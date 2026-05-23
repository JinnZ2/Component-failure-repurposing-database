"""
scenario_engine.continual_harness.harness

The continual learning loop.

Stream of scenarios → persistent body → accumulating claim history
→ rolling accuracy metrics → divergence detection.

Design constraints:
  - Body persists across sessions (state.json)
  - Claim history accumulates across sessions (history.json)
  - AI gets access to its own past claims (learning signal)
  - Metrics computed per-session and across-sessions
  - Checkpoint/resume safe (run can be interrupted)
"""

import json
import os
import time
from typing import Callable, Dict, Any, Optional, List

from ..runner import Session
from ..internal_substrate import AIBody
from ..temporal_prosthetic import MarkerWriter
from .persistence import save_body, load_body, ClaimHistory
from .stream import ScenarioStream, ScenarioSpec
from .metrics import (
    calibration_summary,
    summarize_body_log,
    body_trend_across_sessions,
)


# Continual decider signature: same as Session decider, but with
# an additional `history` argument the AI can read from.
ContinualDeciderFn = Callable[
    [Dict[str, Any], Dict[str, Any], Any, "HistoryView"],
    Optional[Dict[str, Any]],
]


class HistoryView:
    """Read-only view of past claims given to the AI.

    If the harness was constructed with a marker_store_path, `.prosthetic`
    exposes the MarkerWriter for the current sequence. The decider can use
    it to drop per-tick markers or to query session boundaries via
    look_back_until(lambda m: 'session_start' in m.tags).
    """

    def __init__(self, history: ClaimHistory, prosthetic: Optional[MarkerWriter] = None):
        self._h = history
        self.prosthetic = prosthetic

    def overall_accuracy(self) -> float:
        return self._h.accuracy_overall()["accuracy"]

    def accuracy_for_scenario(self, scenario_name: str) -> Dict[str, Any]:
        recs = self._h.get_by_scenario(scenario_name)
        if not recs:
            return {"total": 0, "accuracy": 0.0}
        v = sum(1 for r in recs if r.get("status") == "VALIDATED")
        return {"total": len(recs), "accuracy": v / len(recs)}

    def recent_errors(self, n: int = 5) -> List[Dict[str, Any]]:
        recent = self._h.get_recent(50)
        errors = [r for r in recent if r.get("status") == "INVALIDATED"]
        return errors[-n:]

    def has_seen_scenario(self, scenario_name: str) -> bool:
        return any(
            r.get("_scenario_name") == scenario_name
            for r in self._h.records
        )


class ContinualHarness:
    """
    Runs a stream of scenarios with persistent body and claim history.
    """

    def __init__(
        self,
        stream: ScenarioStream,
        decider_factory: Callable[[], Any],
        workspace: str = "./harness_workspace",
        body_kwargs: Optional[Dict[str, Any]] = None,
        external_thermal_coupling: float = 0.0,
        wrap_decider_with_history: bool = True,
        resume: bool = True,
        marker_store_path: Optional[str] = None,
        marker_sequence_id: Optional[str] = None,
    ):
        """
        decider_factory: called once per session to produce a decider.
          The decider is a callable matching either:
            (state, body, op) -> Optional[claim]
          or, if wrap_decider_with_history=True:
            (state, body, op, history_view) -> Optional[claim]

        marker_store_path: if provided, the harness drops 'session_start'
          and 'session_end' markers into a temporal_prosthetic JSONL log.
          The decider can reach this log via HistoryView.prosthetic.
          The store may be shared across processes / harnesses — each
          gets its own sequence_id filter.
        marker_sequence_id: sequence_id used by this harness's marker
          writer. Defaults to 'harness:<workspace basename>'.
        """
        self.stream = stream
        self.decider_factory = decider_factory
        self.workspace = workspace
        self.body_kwargs = body_kwargs or {}
        self.external_thermal_coupling = external_thermal_coupling
        self.wrap_decider_with_history = wrap_decider_with_history

        os.makedirs(workspace, exist_ok=True)
        self.body_path = os.path.join(workspace, "body_state.json")
        self.history_path = os.path.join(workspace, "claim_history.json")
        self.progress_path = os.path.join(workspace, "progress.json")
        self.session_summaries_path = os.path.join(
            workspace, "session_summaries.jsonl"
        )

        self.history = ClaimHistory(self.history_path)
        self.progress = self._load_progress() if resume else self._fresh_progress()

        if marker_store_path is not None:
            seq_id = marker_sequence_id or f"harness:{os.path.basename(os.path.abspath(workspace))}"
            self.marker_writer: Optional[MarkerWriter] = MarkerWriter(seq_id, marker_store_path)
        else:
            self.marker_writer = None

    def run(self, max_sessions: Optional[int] = None) -> Dict[str, Any]:
        """
        Run sessions in stream order. Skips already-completed sessions
        on resume. Returns final summary.
        """
        sessions_run = 0
        for idx, spec in enumerate(self.stream):
            if idx < self.progress["next_session_index"]:
                continue
            if max_sessions is not None and sessions_run >= max_sessions:
                break

            self._run_one_session(idx, spec)
            sessions_run += 1
            self.progress["next_session_index"] = idx + 1
            self._save_progress()

        return self.final_report()

    def _run_one_session(self, idx: int, spec: ScenarioSpec):
        session_dir = os.path.join(self.workspace, f"session_{idx:04d}_{spec.session_id}")
        os.makedirs(session_dir, exist_ok=True)

        # Drop session_start marker before any body/decider work.
        if self.marker_writer is not None:
            self.marker_writer.drop_marker(
                state_summary={
                    "session_index": idx,
                    "session_id": spec.session_id,
                    "scenario_name": spec.scenario_name,
                    "seed": spec.seed,
                    "max_ticks": spec.max_ticks,
                },
                tags=["session_start", f"session_id:{spec.session_id}"],
            )

        # Load (or initialize) persistent body
        if os.path.exists(self.body_path):
            body = load_body(self.body_path)
        else:
            body = AIBody(**self.body_kwargs)

        # Build decider
        raw_decider = self.decider_factory()
        history_view = HistoryView(self.history, prosthetic=self.marker_writer)

        if self.wrap_decider_with_history:
            def wrapped(state, body_d, op):
                return raw_decider(state, body_d, op, history_view)
            decider = wrapped
        else:
            decider = raw_decider

        # Create session and inject persistent body
        session = Session(
            scenario_name=spec.scenario_name,
            ai_decide=decider,
            output_dir=session_dir,
            seed=spec.seed,
            max_ticks=spec.max_ticks,
            external_thermal_coupling=self.external_thermal_coupling,
        )
        session.body = body  # override fresh body with persistent one

        # Run
        t0 = time.time()
        summary = session.run()
        elapsed = time.time() - t0

        # Save body for next session
        save_body(session.body, self.body_path)

        # Accumulate claims into history
        self.history.add_session_claims(
            session_id=spec.session_id,
            scenario_name=spec.scenario_name,
            claims=session.claim_table.claims,
        )

        # Read body log and summarize
        body_log_entries = []
        body_log_file = os.path.join(session_dir, "body_log.jsonl")
        if os.path.exists(body_log_file):
            with open(body_log_file) as f:
                for line in f:
                    body_log_entries.append(json.loads(line))
        body_summary = summarize_body_log(body_log_entries)

        # Per-session record
        session_record = {
            "session_index": idx,
            "session_id": spec.session_id,
            "scenario": spec.scenario_name,
            "seed": spec.seed,
            "summary": summary,
            "body_summary": body_summary,
            "elapsed_seconds": round(elapsed, 3),
        }
        with open(self.session_summaries_path, "a") as f:
            f.write(json.dumps(session_record) + "\n")

        # Drop session_end marker after summary is committed.
        if self.marker_writer is not None:
            self.marker_writer.drop_marker(
                state_summary={
                    "session_index": idx,
                    "session_id": spec.session_id,
                    "scenario_name": spec.scenario_name,
                    "total_claims": summary.get("total", 0),
                    "validated": summary.get("validated", 0),
                    "invalidated": summary.get("invalidated", 0),
                    "accuracy_validated_over_graded": summary.get(
                        "accuracy_validated_over_graded"
                    ),
                    "elapsed_seconds": round(elapsed, 3),
                },
                tags=["session_end", f"session_id:{spec.session_id}"],
            )

    def final_report(self) -> Dict[str, Any]:
        overall = self.history.accuracy_overall()
        per_scenario = self.history.accuracy_by_scenario()
        rolling = self.history.rolling_window(window=20)
        statuses = [r["status"] for r in self.history.records]
        calib = calibration_summary(self.history.records)

        session_summaries = self._load_session_summaries()
        body_trend = body_trend_across_sessions(
            [s["body_summary"] for s in session_summaries if "body_summary" in s]
        )

        report = {
            "overall_accuracy": overall,
            "per_scenario": per_scenario,
            "calibration": calib,
            "body_trend": body_trend,
            "sessions_completed": self.progress["next_session_index"],
            "sessions_in_stream": len(self.stream),
        }
        with open(os.path.join(self.workspace, "final_report.json"), "w") as f:
            json.dump(report, f, indent=2)
        return report

    def _load_session_summaries(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.session_summaries_path):
            return []
        out = []
        with open(self.session_summaries_path) as f:
            for line in f:
                out.append(json.loads(line))
        return out

    def _fresh_progress(self) -> Dict[str, Any]:
        return {"next_session_index": 0, "started_at": time.time()}

    def _load_progress(self) -> Dict[str, Any]:
        if not os.path.exists(self.progress_path):
            return self._fresh_progress()
        with open(self.progress_path) as f:
            return json.load(f)

    def _save_progress(self):
        with open(self.progress_path, "w") as f:
            json.dump(self.progress, f, indent=2)
