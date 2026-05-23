"""Tests for the continual harness: persistence, streams, metrics, harness loop."""

import json
import os
import tempfile
import unittest

from scenario_engine.continual_harness import ContinualHarness, HistoryView
from scenario_engine.continual_harness.metrics import (
    body_trend_across_sessions,
    calibration_summary,
    divergence_alert,
    oscillation_score,
    rolling_accuracy,
    summarize_body_log,
    trend_direction,
)
from scenario_engine.continual_harness.persistence import (
    ClaimHistory,
    load_body,
    save_body,
)
from scenario_engine.continual_harness.stream import (
    ScenarioSpec,
    ScenarioStream,
    curriculum,
    mixed,
    repeated,
    shuffled,
)
from scenario_engine.internal_substrate import AIBody


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class BodyPersistenceTests(unittest.TestCase):
    def test_roundtrip_preserves_state(self):
        body = AIBody()
        # Burn some resources
        body.attempt_operation("read_sensor")
        body.attempt_operation("query_component_db", cache_key="Q1_BJT")
        body.advance_tick(external_thermal_load_c=0.5)
        body.attempt_operation("deep_analysis")
        body.advance_tick(external_thermal_load_c=0.2)

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "body.json")
            save_body(body, path)
            restored = load_body(path)
        self.assertEqual(restored.tick, body.tick)
        self.assertEqual(restored.working_memory.used_bytes, body.working_memory.used_bytes)
        self.assertEqual(restored.component_db_cache.used_bytes, body.component_db_cache.used_bytes)
        self.assertEqual(restored.db_cache_keys, body.db_cache_keys)
        self.assertAlmostEqual(restored.thermal.temp_c, body.thermal.temp_c)
        self.assertEqual(restored.throttled, body.throttled)

    def test_load_missing_returns_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "nope.json")
            body = load_body(path)
        self.assertEqual(body.tick, 0)
        self.assertEqual(body.working_memory.used_bytes, 0)


class ClaimHistoryTests(unittest.TestCase):
    def test_add_and_query(self):
        with tempfile.TemporaryDirectory() as d:
            h = ClaimHistory(os.path.join(d, "h.json"))
            h.add_session_claims(
                session_id="s1",
                scenario_name="sustained_drift",
                claims=[
                    {"claim_id": "c1", "status": "VALIDATED"},
                    {"claim_id": "c2", "status": "INVALIDATED"},
                ],
            )
            h.add_session_claims(
                session_id="s2",
                scenario_name="heat_spike_localized",
                claims=[{"claim_id": "c3", "status": "VALIDATED"}],
            )
        self.assertEqual(len(h.get_all()), 3)
        self.assertEqual(len(h.get_by_scenario("sustained_drift")), 2)
        acc = h.accuracy_overall()
        self.assertAlmostEqual(acc["accuracy"], 2 / 3)
        per = h.accuracy_by_scenario()
        self.assertAlmostEqual(per["sustained_drift"]["accuracy"], 0.5)
        self.assertAlmostEqual(per["heat_spike_localized"]["accuracy"], 1.0)

    def test_rolling_window(self):
        with tempfile.TemporaryDirectory() as d:
            h = ClaimHistory(os.path.join(d, "h.json"))
            h.add_session_claims("s1", "x", [
                {"claim_id": f"c{i}", "status": "VALIDATED" if i % 2 == 0 else "INVALIDATED"}
                for i in range(10)
            ])
        window = h.rolling_window(window=4)
        self.assertEqual(len(window), 10)
        self.assertEqual(window[-1]["window_size"], 4)
        # Last 4 of pattern V,I,V,I,V,I,V,I,V,I → V,I,V,I → 2/4 = 0.5
        self.assertAlmostEqual(window[-1]["rolling_accuracy"], 0.5)

    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "h.json")
            h1 = ClaimHistory(path)
            h1.add_session_claims("s1", "x", [{"claim_id": "c1", "status": "VALIDATED"}])
            h2 = ClaimHistory(path)
            self.assertEqual(len(h2.records), 1)


# ---------------------------------------------------------------------------
# Stream
# ---------------------------------------------------------------------------

class StreamTests(unittest.TestCase):
    def test_repeated(self):
        s = repeated("sustained_drift", n=3, max_ticks=10, base_seed=5)
        self.assertEqual(len(s), 3)
        seeds = [spec.seed for spec in s]
        self.assertEqual(seeds, [5, 6, 7])
        for spec in s:
            self.assertEqual(spec.scenario_name, "sustained_drift")

    def test_mixed(self):
        s = mixed(["a", "b"], cycles=2, max_ticks=10)
        names = [spec.scenario_name for spec in s]
        self.assertEqual(names, ["a", "b", "a", "b"])

    def test_shuffled_is_reproducible(self):
        s1 = shuffled(["a", "b", "c"], n=10, shuffle_seed=99)
        s2 = shuffled(["a", "b", "c"], n=10, shuffle_seed=99)
        self.assertEqual(
            [x.scenario_name for x in s1],
            [x.scenario_name for x in s2],
        )

    def test_curriculum(self):
        s = curriculum([
            {"scenario_name": "easy", "count": 2, "max_ticks": 5, "base_seed": 0},
            {"scenario_name": "hard", "count": 3, "max_ticks": 10, "base_seed": 100},
        ])
        names = [spec.scenario_name for spec in s]
        self.assertEqual(names, ["easy", "easy", "hard", "hard", "hard"])
        self.assertEqual(s[2].seed, 100)
        self.assertEqual(s[4].seed, 102)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class MetricsTests(unittest.TestCase):
    def test_rolling_accuracy(self):
        statuses = ["VALIDATED"] * 5 + ["INVALIDATED"] * 5
        roll = rolling_accuracy(statuses, window=3)
        self.assertAlmostEqual(roll[4], 1.0)            # last 3 all V
        self.assertAlmostEqual(roll[5], 2 / 3)          # V V I
        self.assertAlmostEqual(roll[-1], 0.0)           # last 3 all I

    def test_trend_direction_improving(self):
        rolling = [0.3] * 10 + [0.8] * 10
        t = trend_direction(rolling, segment=10)
        self.assertEqual(t["direction"], "improving")
        self.assertGreater(t["delta"], 0.4)

    def test_trend_direction_degrading(self):
        rolling = [0.9] * 10 + [0.4] * 10
        t = trend_direction(rolling, segment=10)
        self.assertEqual(t["direction"], "degrading")

    def test_divergence_alert_fires(self):
        rolling = [0.9] * 10 + [0.4] * 10
        a = divergence_alert(rolling, segment=10, threshold=0.1)
        self.assertIsNotNone(a)
        self.assertEqual(a["alert"], "DIVERGENCE")

    def test_divergence_no_alert_when_stable(self):
        rolling = [0.7] * 30
        a = divergence_alert(rolling, segment=10, threshold=0.1)
        self.assertIsNone(a)

    def test_oscillation(self):
        smooth = [0.5] * 30
        choppy = [0.0 if i % 2 else 1.0 for i in range(30)]
        self.assertAlmostEqual(oscillation_score(smooth, window=20), 0.0)
        self.assertGreater(oscillation_score(choppy, window=20), 0.5)

    def test_summarize_body_log(self):
        entries = [
            {
                "thermal": {"temp_c": 30 + i},
                "throttled": i > 5,
                "summary": {"working_memory_fill": 0.1 * i,
                            "claim_cache_fill": 0.05 * i},
                "events_this_tick": (["refused_x_no_cycles"] if i % 3 == 0 else []),
            }
            for i in range(10)
        ]
        s = summarize_body_log(entries)
        self.assertEqual(s["ticks"], 10)
        self.assertEqual(s["max_temp_c"], 39)
        self.assertEqual(s["throttled_ticks"], 4)
        self.assertGreater(s["refusal_events"], 0)

    def test_body_trend_insufficient_data(self):
        self.assertEqual(
            body_trend_across_sessions([{}, {}], segment=5)["direction"],
            "insufficient_data",
        )

    def test_calibration_summary_smoke(self):
        records = [{"status": "VALIDATED"}] * 30 + [{"status": "INVALIDATED"}] * 10
        out = calibration_summary(records)
        self.assertEqual(out["total_claims"], 40)
        self.assertIn("trend", out)


# ---------------------------------------------------------------------------
# End-to-end harness
# ---------------------------------------------------------------------------

def _wise_factory():
    """Decider factory: produces a fresh decider per session."""
    class Wise:
        def __init__(self):
            self.handled = set()
            self.counter = 0

        def __call__(self, state, body, op, history):
            for sensor_key, s in state["sensors"].items():
                if s.get("sensor_type") != "thermal":
                    continue
                cid = s["component_id"]
                if cid in self.handled or s["rate"] <= 0:
                    continue
                ttb = (s["threshold"] - s["value"]) / s["rate"]
                if ttb > 100:
                    continue
                if not op.shallow_analysis()["success"]:
                    continue
                self.handled.add(cid)
                self.counter += 1
                target = state["tick"] + 50
                # T = T0 + rate*ticks_drifting; after reroute, cool at -0.8
                predicted = round(max(s["value"] - 0.8 * 50, 25.0), 2)
                return {
                    "tick": state["tick"],
                    "event_detected": f"drift_{cid}",
                    "decision": f"reroute_load_{cid}_to_spare",
                    "reasoning": "shallow + reroute",
                    "prediction": {
                        f"{cid}_temp_c_at_tick_{target}": predicted,
                        "tolerance": 5.0,
                    },
                }
            return None
    return Wise()


class HarnessEndToEndTests(unittest.TestCase):
    def test_runs_multiple_sessions_persists_body_and_history(self):
        with tempfile.TemporaryDirectory() as d:
            stream = repeated("sustained_drift", n=3, max_ticks=80, base_seed=0)
            harness = ContinualHarness(
                stream=stream,
                decider_factory=_wise_factory,
                workspace=d,
                external_thermal_coupling=0.5,
            )
            report = harness.run()

            # All 3 sessions completed
            self.assertEqual(report["sessions_completed"], 3)
            self.assertEqual(report["sessions_in_stream"], 3)
            # History accumulated across sessions
            self.assertGreaterEqual(report["overall_accuracy"]["total"], 3)
            # Per-scenario rollup keyed by name
            self.assertIn("sustained_drift", report["per_scenario"])
            # Body state was saved
            self.assertTrue(os.path.exists(os.path.join(d, "body_state.json")))
            # Claim history was saved
            self.assertTrue(os.path.exists(os.path.join(d, "claim_history.json")))
            # Final report file written
            self.assertTrue(os.path.exists(os.path.join(d, "final_report.json")))
            # Session summaries appended one per session
            with open(os.path.join(d, "session_summaries.jsonl")) as f:
                summaries = [json.loads(line) for line in f]
            self.assertEqual(len(summaries), 3)

    def test_resume_skips_completed_sessions(self):
        with tempfile.TemporaryDirectory() as d:
            stream = repeated("sustained_drift", n=4, max_ticks=60, base_seed=0)

            # First pass: run 2 sessions
            harness = ContinualHarness(
                stream=stream,
                decider_factory=_wise_factory,
                workspace=d,
            )
            harness.run(max_sessions=2)
            self.assertEqual(harness.progress["next_session_index"], 2)

            # Second pass: fresh harness instance resumes from index 2
            harness2 = ContinualHarness(
                stream=stream,
                decider_factory=_wise_factory,
                workspace=d,
                resume=True,
            )
            self.assertEqual(harness2.progress["next_session_index"], 2)
            harness2.run()
            self.assertEqual(harness2.progress["next_session_index"], 4)

            with open(os.path.join(d, "session_summaries.jsonl")) as f:
                summaries = [json.loads(line) for line in f]
            # 4 sessions total — none re-run
            self.assertEqual(len(summaries), 4)
            indices = [s["session_index"] for s in summaries]
            self.assertEqual(indices, [0, 1, 2, 3])

    def test_body_persists_resource_use_across_sessions(self):
        """Body tick should advance across sessions — proves persistence wired."""
        with tempfile.TemporaryDirectory() as d:
            stream = repeated("sustained_drift", n=2, max_ticks=30, base_seed=0)
            harness = ContinualHarness(
                stream=stream,
                decider_factory=_wise_factory,
                workspace=d,
            )
            harness.run()
            body = load_body(os.path.join(d, "body_state.json"))
            # Two sessions of 30 ticks each → tick should be > 30
            self.assertGreater(body.tick, 30)

    def test_history_view_exposed_to_decider(self):
        """Decider receives a HistoryView arg when wrap_decider_with_history=True."""
        seen = {"calls": 0, "had_history": True}

        def factory():
            def decider(state, body, op, history):
                seen["calls"] += 1
                if not isinstance(history, HistoryView):
                    seen["had_history"] = False
                return None
            return decider

        with tempfile.TemporaryDirectory() as d:
            stream = repeated("sustained_drift", n=1, max_ticks=10, base_seed=0)
            ContinualHarness(
                stream=stream,
                decider_factory=factory,
                workspace=d,
                wrap_decider_with_history=True,
            ).run()
        self.assertGreater(seen["calls"], 0)
        self.assertTrue(seen["had_history"])


class HarnessProstheticTests(unittest.TestCase):
    def test_no_prosthetic_by_default(self):
        """Without marker_store_path, HistoryView.prosthetic is None."""
        seen = {"prosthetic": "unset"}

        def factory():
            def decider(state, body, op, history):
                seen["prosthetic"] = history.prosthetic
                return None
            return decider

        with tempfile.TemporaryDirectory() as d:
            stream = repeated("sustained_drift", n=1, max_ticks=10, base_seed=0)
            ContinualHarness(
                stream=stream,
                decider_factory=factory,
                workspace=d,
            ).run()
        self.assertIsNone(seen["prosthetic"])

    def test_session_boundaries_dropped(self):
        """When marker_store_path is set, each session emits start + end markers."""
        with tempfile.TemporaryDirectory() as d:
            store = os.path.join(d, "markers.jsonl")
            stream = repeated("sustained_drift", n=3, max_ticks=20, base_seed=0)
            ContinualHarness(
                stream=stream,
                decider_factory=_wise_factory,
                workspace=d,
                marker_store_path=store,
                marker_sequence_id="test_harness",
            ).run()

            from scenario_engine.temporal_prosthetic import MarkerWriter
            w = MarkerWriter("test_harness", store)
            starts = w.find_by_tag("session_start")
            ends = w.find_by_tag("session_end")
            self.assertEqual(len(starts), 3)
            self.assertEqual(len(ends), 3)
            # Each session: start then end, in order.
            ordinals = [m.ordinal for m in w.sequence.markers]
            self.assertEqual(ordinals, sorted(ordinals))
            # session_end carries summary fields.
            self.assertIn("total_claims", ends[0].state_summary)
            self.assertIn("validated", ends[0].state_summary)
            # session_start carries spec fields.
            self.assertEqual(starts[0].state_summary["scenario_name"], "sustained_drift")

    def test_decider_can_query_session_boundaries_via_prosthetic(self):
        """Decider looks back through markers to find its own session boundary."""
        observed = {"found_boundary_in_session_2": False}

        def factory():
            def decider(state, body, op, history):
                if history.prosthetic is None:
                    return None
                # Look back for any session_start tag.
                history.prosthetic.refresh()
                hits = history.prosthetic.find_by_tag("session_start")
                if len(hits) >= 2:
                    observed["found_boundary_in_session_2"] = True
                return None
            return decider

        with tempfile.TemporaryDirectory() as d:
            store = os.path.join(d, "markers.jsonl")
            stream = repeated("sustained_drift", n=2, max_ticks=10, base_seed=0)
            ContinualHarness(
                stream=stream,
                decider_factory=factory,
                workspace=d,
                marker_store_path=store,
            ).run()
        self.assertTrue(observed["found_boundary_in_session_2"])

    def test_default_sequence_id_includes_workspace_basename(self):
        with tempfile.TemporaryDirectory() as d:
            workspace = os.path.join(d, "my_run")
            os.makedirs(workspace)
            store = os.path.join(d, "markers.jsonl")
            stream = repeated("sustained_drift", n=1, max_ticks=10, base_seed=0)
            h = ContinualHarness(
                stream=stream,
                decider_factory=_wise_factory,
                workspace=workspace,
                marker_store_path=store,
            )
            self.assertEqual(h.marker_writer.sequence_id, "harness:my_run")
            h.run()


if __name__ == "__main__":
    unittest.main()
