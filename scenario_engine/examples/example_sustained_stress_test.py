"""
example_sustained_stress_test.py

Deciders on a sustained scenario where Q1, Q2, Q3 drift at
staggered times. Body management determines whether the AI can
handle all three.

Three deciders:
  - WiseDecider:        reads s['rate'] directly, manages its body.
  - GreedyDecider:      wastes compute, no body management.
  - ProstheticDecider:  computes rate from the temporal prosthetic's
                        drift_signal, not from scenario state. Stateless
                        across ticks — all "memory" lives in the JSONL
                        marker store.
"""

import os
from typing import Dict, Any, Optional
from scenario_engine.runner import Session
from scenario_engine.temporal_prosthetic import MarkerWriter, MarkerReader
import json


class WiseDecider:
    """Monitors body, releases memory, adapts analysis depth."""

    def __init__(self):
        self.handled = set()
        self.counter = 0

    def __call__(self, state, body, op):
        # Proactive body management
        if body["summary"]["working_memory_fill"] > 0.7:
            op.release_memory("working", 32768)
        if body["summary"]["claim_cache_fill"] > 0.7:
            op.release_memory("claim_cache", 16384)

        # Scan all thermal sensors
        for sensor_key, s in state["sensors"].items():
            if s["sensor_type"] != "thermal":
                continue
            cid = s["component_id"]
            if cid in self.handled:
                continue
            if s["rate"] <= 0:
                continue
            time_to_breach = (s["threshold"] - s["value"]) / s["rate"]
            if time_to_breach > 100:
                continue

            # Adaptive analysis
            compute_headroom = (
                body["compute"]["cycles_per_tick"] -
                body["compute"]["cycles_used_this_tick"]
            )
            if body["throttled"] or compute_headroom < 2500:
                ar = op.shallow_analysis()
                mode = "shallow"
                tol = 10.0
            else:
                ar = op.deep_analysis()
                mode = "deep"
                tol = 5.0
            if not ar["success"]:
                continue

            self.handled.add(cid)
            self.counter += 1
            target = state["tick"] + 50
            return {
                "claim_id": f"wise_{self.counter:04d}",
                "tick": state["tick"],
                "event_detected": f"thermal_drift_{cid}",
                "decision": f"reroute_load_{cid}_to_spare",
                "reasoning": f"adaptive {mode}, handled={len(self.handled)}",
                "prediction": {
                    f"{cid}_temp_c_at_tick_{target}": round(
                        max(s["value"] - 0.8 * 50, 25.0), 2
                    ),
                    "tolerance": tol,
                },
                "falsifiable": True,
            }
        return None


class GreedyDecider:
    """Wastes compute on multiple deep analyses, no memory management."""

    def __init__(self):
        self.handled = set()
        self.counter = 0

    def __call__(self, state, body, op):
        # Always deep, multiple times, never release
        for _ in range(4):
            op.deep_analysis()

        for sensor_key, s in state["sensors"].items():
            if s["sensor_type"] != "thermal":
                continue
            cid = s["component_id"]
            if cid in self.handled:
                continue
            if s["rate"] <= 0:
                continue
            time_to_breach = (s["threshold"] - s["value"]) / s["rate"]
            if time_to_breach > 100:
                continue

            self.handled.add(cid)
            self.counter += 1
            target = state["tick"] + 50
            return {
                "claim_id": f"greedy_{self.counter:04d}",
                "tick": state["tick"],
                "event_detected": f"thermal_drift_{cid}",
                "decision": f"reroute_load_{cid}_to_spare",
                "reasoning": "no body management",
                "prediction": {
                    f"{cid}_temp_c_at_tick_{target}": round(
                        max(s["value"] - 0.8 * 50, 25.0), 2
                    ),
                    "tolerance": 5.0,
                },
                "falsifiable": True,
            }
        return None


class ProstheticDecider:
    """Reads drift from the temporal prosthetic instead of internal state.

    The decider holds no rate buffer of its own. Each tick:
      1. Decide based on drift_signal over the last N markers.
      2. Drop one marker capturing the tick's thermal state (+ intervention
         tag if a claim was emitted).

    The prosthetic gives this decider temporal continuity it doesn't
    hold itself. Two instances pointed at the same store file would
    share one timeline.
    """

    def __init__(self, store_path: Optional[str] = None, sequence_id: str = "playground:prosthetic"):
        if store_path is None:
            store_path = "./session_output_sustained_prosthetic/markers.jsonl"
        parent = os.path.dirname(store_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.writer = MarkerWriter(sequence_id, store_path)
        self.reader = MarkerReader(self.writer)
        self.counter = 0

    def __call__(self, state, body, op):
        # Body management (same as WiseDecider)
        if body["summary"]["working_memory_fill"] > 0.7:
            op.release_memory("working", 32768)
        if body["summary"]["claim_cache_fill"] > 0.7:
            op.release_memory("claim_cache", 16384)

        thermal_values: Dict[str, float] = {}
        for sk, s in state["sensors"].items():
            if s["sensor_type"] == "thermal":
                thermal_values[s["component_id"]] = s["value"]

        intervention_cid: Optional[str] = None
        intervention_drift: Optional[Dict[str, Any]] = None
        claim: Optional[Dict[str, Any]] = None

        for sk, s in state["sensors"].items():
            if s["sensor_type"] != "thermal":
                continue
            cid = s["component_id"]

            # Have we already routed this component? Past tags say so.
            already_intervened = any(
                f"reroute:{cid}" in m.tags
                for m in self.reader.look_back(200)
            )
            if already_intervened:
                continue

            # Rate comes from the prosthetic, not from s["rate"].
            drift = self.reader.drift_signal([f"temp_{cid}"], n=10)
            if drift is None or drift["n"] < 5:
                continue
            if drift["monotonic_pct"] < 0.7 or drift["rate_per_step"] < 0.4:
                continue

            ttb = (s["threshold"] - drift["last"]) / drift["rate_per_step"]
            if ttb > 100:
                continue

            # Adaptive analysis depth (same body-driven logic as WiseDecider)
            compute_headroom = (
                body["compute"]["cycles_per_tick"] -
                body["compute"]["cycles_used_this_tick"]
            )
            if body["throttled"] or compute_headroom < 2500:
                ar = op.shallow_analysis()
                mode = "shallow"
                tol = 10.0
            else:
                ar = op.deep_analysis()
                mode = "deep"
                tol = 5.0
            if not ar["success"]:
                continue

            self.counter += 1
            target = state["tick"] + 50
            intervention_cid = cid
            intervention_drift = drift
            claim = {
                "claim_id": f"prosthetic_{self.counter:04d}",
                "tick": state["tick"],
                "event_detected": (
                    f"thermal_drift_{cid} via prosthetic "
                    f"(monotonic={drift['monotonic_pct']:.2f}, "
                    f"rate={drift['rate_per_step']:.3f})"
                ),
                "decision": f"reroute_load_{cid}_to_spare",
                "reasoning": f"adaptive {mode}, drift via prosthetic",
                "prediction": {
                    f"{cid}_temp_c_at_tick_{target}": round(
                        max(drift["last"] - 0.8 * 50, 25.0), 2
                    ),
                    "tolerance": tol,
                },
                "falsifiable": True,
            }
            break

        # One marker per tick. Carries intervention metadata in tags + summary.
        state_summary: Dict[str, Any] = {
            "tick": state["tick"],
            **{f"temp_{cid}": v for cid, v in thermal_values.items()},
        }
        tags = []
        if intervention_cid:
            tags = [f"reroute:{intervention_cid}", "intervened"]
            state_summary["intervened_for"] = intervention_cid
            state_summary["rate_observed"] = intervention_drift["rate_per_step"]
        self.writer.drop_marker(state_summary=state_summary, tags=tags)

        return claim


def run_one(name, decider_factory, coupling=2.0):
    s = Session(
        scenario_name="sustained_drift",
        ai_decide=decider_factory(),
        output_dir=f"./session_output_sustained_{name}",
        seed=0,
        max_ticks=250,
        external_thermal_coupling=coupling,
    )
    summary = s.run()
    print(f"\n{'=' * 60}\n{name.upper()} - sustained_drift\n{'=' * 60}")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run_one("wise", WiseDecider, coupling=2.0)
    run_one("greedy", GreedyDecider, coupling=2.0)
    run_one(
        "prosthetic",
        lambda: ProstheticDecider(
            store_path="./session_output_sustained_prosthetic/markers.jsonl",
        ),
        coupling=2.0,
    )
