"""
example_sustained_stress_test.py

Three deciders on a sustained scenario where Q1, Q2, Q3
drift at staggered times. Body management determines whether
the AI can handle all three.
"""

from typing import Dict, Any, Optional
from scenario_engine.runner import Session
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


def run_one(name, decider_cls, coupling=2.0):
    s = Session(
        scenario_name="sustained_drift",
        ai_decide=decider_cls(),
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
