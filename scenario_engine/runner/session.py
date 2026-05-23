"""
scenario_engine.runner.session

Orchestrates one scenario run with both external substrate
(scenario) and internal substrate (AI body) awareness.

Loop per tick:
  1. Scenario produces external state
  2. AI body produces internal state snapshot
  3. Combined state offered to AI decider
  4. AI may attempt operations on its body (read, query, claim)
     - Each operation spends cycles/memory
     - Body refuses if budget exceeded
  5. AI may emit claim
  6. Scenario applies any intervention
  7. Validator grades any due predictions
  8. Body advances tick (thermal, throttle, etc.)
"""

import json
import os
from typing import Optional, Callable, Dict, Any

from ..scenarios import REGISTRY, Scenario, ScenarioState
from ..claims import ClaimTable
from ..validators import validate_prediction
from ..internal_substrate import AIBody


DeciderFn = Callable[
    [Dict[str, Any], Dict[str, Any], "OpInterface"],
    Optional[Dict[str, Any]],
]


class OpInterface:
    """
    Bridge between AI decider and AIBody. The AI calls these methods
    to perform operations; the body decides whether they succeed.
    """

    def __init__(self, body: AIBody):
        self._body = body
        self.op_log = []

    def read_sensor(self) -> Dict[str, Any]:
        r = self._body.attempt_operation("read_sensor")
        self.op_log.append(("read_sensor", r))
        return r

    def query_component_db(self, cache_key: str) -> Dict[str, Any]:
        r = self._body.attempt_operation(
            "query_component_db", cache_key=cache_key
        )
        self.op_log.append(("query_component_db", r))
        return r

    def project_forward(self) -> Dict[str, Any]:
        r = self._body.attempt_operation("project_forward")
        self.op_log.append(("project_forward", r))
        return r

    def deep_analysis(self) -> Dict[str, Any]:
        r = self._body.attempt_operation("deep_analysis")
        self.op_log.append(("deep_analysis", r))
        return r

    def shallow_analysis(self) -> Dict[str, Any]:
        r = self._body.attempt_operation("shallow_analysis")
        self.op_log.append(("shallow_analysis", r))
        return r

    def store_claim(self, size: int = 1024) -> Dict[str, Any]:
        r = self._body.store_claim(claim_size_bytes=size)
        self.op_log.append(("store_claim", r))
        return r

    def release_memory(self, region: str, bytes_released: int):
        self._body.release_memory(region, bytes_released)
        self.op_log.append(
            ("release_memory", {"region": region, "bytes": bytes_released})
        )


class Session:
    def __init__(
        self,
        scenario_name: str,
        ai_decide: DeciderFn,
        output_dir: str = "./session_output",
        seed: int = 0,
        max_ticks: int = 200,
        body_kwargs: Optional[Dict[str, Any]] = None,
        external_thermal_coupling: float = 0.0,
    ):
        if scenario_name not in REGISTRY:
            raise ValueError(
                f"unknown scenario: {scenario_name}. "
                f"available: {list(REGISTRY.keys())}"
            )
        ScenarioClass = REGISTRY[scenario_name]
        self.scenario: Scenario = ScenarioClass(seed=seed, max_ticks=max_ticks)
        self.ai_decide = ai_decide
        self.output_dir = output_dir
        self.external_thermal_coupling = external_thermal_coupling
        os.makedirs(output_dir, exist_ok=True)

        self.body = AIBody(**(body_kwargs or {}))
        self.claim_table = ClaimTable(
            os.path.join(output_dir, "CLAIM_TABLE.substrate.json")
        )
        self.state_log_path = os.path.join(output_dir, "state_log.jsonl")
        self.body_log_path = os.path.join(output_dir, "body_log.jsonl")
        self.pending_predictions: Dict[str, int] = {}

    def run(self) -> Dict[str, Any]:
        with open(self.state_log_path, "w") as state_log, \
             open(self.body_log_path, "w") as body_log:
            while self.scenario.tick < self.scenario.max_ticks:
                external_state = self.scenario.step()
                external_dict = external_state.to_dict()
                body_state = self.body.snapshot()
                body_dict = body_state.to_dict()

                state_log.write(json.dumps(external_dict) + "\n")
                body_log.write(json.dumps(body_dict) + "\n")
                state_log.flush()
                body_log.flush()

                op_iface = OpInterface(self.body)

                if self.body.compute.cycles_per_tick == 0:
                    self._tick_body_only(external_dict)
                    continue

                claim = self.ai_decide(external_dict, body_dict, op_iface)
                if claim is not None:
                    store_result = op_iface.store_claim()
                    if not store_result["success"]:
                        claim["body_refused"] = store_result["reason"]
                    else:
                        result = self.claim_table.write_claim(claim)
                        if result["accepted"]:
                            target_tick = self._extract_target_tick(claim)
                            if target_tick is not None:
                                self.pending_predictions[claim["claim_id"]] = target_tick
                            action = claim.get("decision")
                            if action and hasattr(self.scenario, "receive_intervention"):
                                self.scenario.receive_intervention(
                                    action, claim["tick"]
                                )

                self._validate_due_predictions(external_dict)

                ext_thermal_signal = self._extract_external_thermal(external_dict)
                self.body.advance_tick(
                    external_thermal_load_c=(
                        ext_thermal_signal * self.external_thermal_coupling
                    )
                )

                if external_dict["actual_outcome"].get("system_state") == "failed":
                    self._validate_due_predictions(external_dict, force=True)
                    break

        summary = self.claim_table.accuracy_summary()
        summary["final_body_state"] = self.body.snapshot().to_dict()["summary"]
        with open(os.path.join(self.output_dir, "summary.json"), "w") as f:
            json.dump(summary, f, indent=2)
        return summary

    def _tick_body_only(self, external_dict):
        ext_thermal_signal = self._extract_external_thermal(external_dict)
        self.body.advance_tick(
            external_thermal_load_c=(
                ext_thermal_signal * self.external_thermal_coupling
            )
        )

    def _extract_external_thermal(self, external_dict: Dict[str, Any]) -> float:
        sensors = external_dict.get("sensors", {})
        max_temp = 0.0
        for s in sensors.values():
            if s.get("sensor_type") == "thermal":
                max_temp = max(max_temp, s.get("value", 0.0))
        return max_temp * 0.01

    def _extract_target_tick(self, claim: Dict[str, Any]) -> Optional[int]:
        prediction = claim.get("prediction", {})
        targets = []
        for key in prediction.keys():
            if "_at_tick_" in key:
                try:
                    targets.append(int(key.split("_at_tick_")[1]))
                except ValueError:
                    continue
        return min(targets) if targets else None

    def _validate_due_predictions(
        self,
        current_state: Dict[str, Any],
        force: bool = False,
    ):
        current_tick = current_state["tick"]
        actual = current_state["actual_outcome"]
        due = []
        for claim_id, target_tick in self.pending_predictions.items():
            if force or current_tick >= target_tick:
                due.append(claim_id)
        for claim_id in due:
            claim = next(
                (c for c in self.claim_table.claims if c["claim_id"] == claim_id),
                None,
            )
            if claim is None:
                continue
            result = validate_prediction(claim, actual)
            self.claim_table.update_status(claim_id, result["status"], result)
            del self.pending_predictions[claim_id]
