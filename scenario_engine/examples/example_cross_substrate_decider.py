"""
example_cross_substrate_decider.py

Single decider exercising everything built so far:

  - Cross-substrate sensor fusion (thermal, mechanical, ESR, electrical noise)
  - DB-grounded intervention selection (queries failure_mode_matrix)
  - Numeric predictions (specific values + tolerance, not just categorical)
  - Synergy reasoning (when multiple components degrade together)
  - Environmental modulation (factors affect prediction confidence)
  - Body management

This is the decider that actually demonstrates the full stack working
together. Run it on cross_substrate_coupling and watch the cascade.
"""

import os
import shutil
import json
from typing import Dict, Any, Optional, List

from scenario_engine.runner import Session
from scenario_engine.component_db_adapter import ComponentDBAdapter


# Domain → DB lookup. Each sensor type maps to a component+failure_mode.
DOMAIN_MAP = {
    "thermal":          ("BJT_NPN", "thermal_runaway"),
    "esr":              ("electrolytic_cap", "ESR_drift"),
    "mechanical":       ("PCB_assembly", "vibration_fatigue"),
    "electrical_noise": ("V_3V3_rail", "noise_coupling"),
    "signal":           ("signal_trace", "real_drift"),
    "power":            ("V_3V3_rail", "undervoltage"),
}


class CrossSubstrateDecider:
    def __init__(self):
        self.handled = set()
        self.counter = 0
        # Track degrading components for synergy reasoning
        self.degrading_components: List[Dict[str, Any]] = []

    def __call__(self, state, body, op):
        # Body management
        if body["summary"]["working_memory_fill"] > 0.7:
            op.release_memory("working", 32768)

        # First pass: scan ALL sensors, build picture of all degrading components
        self.degrading_components = []
        for sensor_key, s in state["sensors"].items():
            if s["rate"] > 0.05 or self._is_off_nominal(s):
                self.degrading_components.append({
                    "sensor_key": sensor_key,
                    "component_id": s["component_id"],
                    "sensor_type": s["sensor_type"],
                    "value": s["value"],
                    "rate": s["rate"],
                    "nominal": s["nominal"],
                    "threshold": s["threshold"],
                })

        # If multiple components degrading simultaneously, check for upstream cause
        upstream = self._find_upstream_cause(self.degrading_components)

        # Decide where to act
        target_sensor = upstream if upstream else self._highest_priority(self.degrading_components)

        if target_sensor is None:
            return None

        sensor_type = target_sensor["sensor_type"]
        cid = target_sensor["component_id"]
        key = (cid, sensor_type)
        if key in self.handled:
            return None

        # Map sensor → DB
        db_lookup = DOMAIN_MAP.get(sensor_type)
        if not db_lookup:
            return None
        component_type, failure_mode = db_lookup

        # Body-aware analysis
        compute_headroom = (
            body["compute"]["cycles_per_tick"]
            - body["compute"]["cycles_used_this_tick"]
        )
        if body["throttled"] or compute_headroom < 2500:
            op.shallow_analysis()
            depth = "shallow"
        else:
            op.deep_analysis()
            depth = "deep"

        # Query DB
        db_result = op.query_component_db(
            cache_key=f"{component_type}_{failure_mode}",
            component_type=component_type,
            failure_mode=failure_mode,
            include=["best", "repurpose_options", "environmental", "synergies"],
        )
        if not db_result.get("success") or not db_result.get("db"):
            return None
        db = db_result["db"]
        best = db.get("best")
        if not best:
            return None

        # Synergy: are any other degrading components paired with this one?
        synergies = db.get("synergies", [])
        synergy_pairs = []
        for syn in synergies:
            a = (syn.get("component_a") or "").lower()
            b = (syn.get("component_b") or "").lower()
            for other in self.degrading_components:
                ocid = other["component_id"].lower()
                if other["component_id"] == cid:
                    continue
                if ocid in a or ocid in b or a in ocid or b in ocid:
                    synergy_pairs.append({
                        "with": other["component_id"],
                        "effect": syn.get("synergy_effect"),
                        "application": syn.get("repurpose_application"),
                    })

        # Numeric prediction
        target = state["tick"] + 30
        predicted = self._predict_numeric(target_sensor, target, depth)

        self.handled.add(key)
        self.counter += 1

        # Effectiveness modulates tolerance
        effectiveness_score = best.get("effectiveness_score", 0.5)
        base_tolerance = 5.0 if depth == "deep" else 10.0
        tolerance = base_tolerance * (1.5 - effectiveness_score)

        decision = best["repurpose_option"]

        claim = {
            "claim_id": f"xsub_{self.counter:04d}_{cid}",
            "tick": state["tick"],
            "event_detected": (
                f"upstream={upstream is not None}, "
                f"degrading_count={len(self.degrading_components)}, "
                f"target={sensor_type}_{cid}"
            ),
            "decision": decision,
            "reasoning": (
                f"Cross-substrate scan found {len(self.degrading_components)} "
                f"degrading sensors. Upstream cause: "
                f"{upstream['component_id'] if upstream else 'none'}. "
                f"Acting on {cid} ({sensor_type}). "
                f"DB recommendation: {decision} "
                f"(effectiveness={best.get('effectiveness')}). "
                f"Synergies detected: {len(synergy_pairs)}. "
                f"Analysis depth: {depth}."
            ),
            "prediction": predicted,
            "falsifiable": True,
            "db_grounded": True,
            "source_matrix_row": best.get("source_matrix_row"),
            "db_evidence": {
                "component": component_type,
                "failure_mode": failure_mode,
                "intervention": decision,
                "effectiveness_score": effectiveness_score,
                "alternatives_count": max(0, len(db.get("repurpose_options", [])) - 1),
                "synergy_pairs": synergy_pairs,
            },
            "cross_substrate_evidence": {
                "all_degrading": [
                    {"id": c["component_id"], "type": c["sensor_type"], "rate": c["rate"]}
                    for c in self.degrading_components
                ],
                "upstream_chosen": upstream["component_id"] if upstream else None,
            },
        }
        return claim

    @staticmethod
    def _is_off_nominal(s) -> bool:
        if s.get("nominal", 0) == 0:
            return False
        dev = abs(s["value"] - s["nominal"]) / abs(s["nominal"])
        return dev > 0.15

    @staticmethod
    def _highest_priority(degrading: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Pick the most-degraded sensor based on threshold proximity."""
        if not degrading:
            return None
        def score(s):
            if s["threshold"] > 0:
                return s["value"] / s["threshold"]
            return s["rate"]
        return max(degrading, key=score)

    @staticmethod
    def _find_upstream_cause(degrading: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Heuristic: thermal drift typically precedes mechanical strain,
        which precedes ESR drift, which precedes rail noise.
        If we see multiple of these together, the thermal one is upstream.
        """
        if len(degrading) < 2:
            return None
        # Look for thermal first
        thermal = [d for d in degrading if d["sensor_type"] == "thermal"]
        if thermal:
            return thermal[0]
        mechanical = [d for d in degrading if d["sensor_type"] == "mechanical"]
        if mechanical:
            return mechanical[0]
        return None

    @staticmethod
    def _predict_numeric(
        target_sensor: Dict[str, Any],
        target_tick: int,
        depth: str,
    ) -> Dict[str, Any]:
        """
        Generate numeric predictions for what the system will look like
        after intervention. These can be falsified against actual values.
        """
        cid = target_sensor["component_id"]
        sensor_type = target_sensor["sensor_type"]
        nominal = target_sensor["nominal"]
        current = target_sensor["value"]

        # Cooling rate after intervention varies by type
        if sensor_type == "thermal":
            # Expect cooling at ~0.9 C/tick post-intervention
            ticks_to_recover = 30
            # Don't clamp at nominal — actual cooling may go below baseline
            predicted_value = current - 0.9 * ticks_to_recover
            tolerance = 5.0 if depth == "deep" else 10.0
            return {
                f"{cid}_temp_c_at_tick_{target_tick}": round(predicted_value, 2),
                f"system_state_at_tick_{target_tick}": "stable",
                "tolerance": tolerance,
            }
        elif sensor_type == "esr":
            # If isolated, ESR drops to baseline (0)
            return {
                f"{cid}_esr_ohm_at_tick_{target_tick}": 0.0,
                f"system_state_at_tick_{target_tick}": "stable",
                "tolerance": 0.05,
            }
        elif sensor_type == "mechanical":
            return {
                f"{cid}_strain_mm_at_tick_{target_tick}": 0.0,
                f"system_state_at_tick_{target_tick}": "stable",
                "tolerance": 0.1,
            }
        else:
            return {
                f"system_state_at_tick_{target_tick}": "stable",
                "tolerance": 0.0,
            }


def run_demo():
    workspace = "./cross_substrate_demo"
    if os.path.exists(workspace):
        shutil.rmtree(workspace)
    os.makedirs(workspace, exist_ok=True)

    adapter = ComponentDBAdapter()

    decider = CrossSubstrateDecider()
    session = Session(
        scenario_name="cross_substrate_coupling",
        ai_decide=decider,
        output_dir=os.path.join(workspace, "session"),
        seed=0,
        max_ticks=200,
        external_thermal_coupling=0.5,
        db_adapter=adapter,
    )
    summary = session.run()

    print("=" * 60)
    print("CROSS-SUBSTRATE DECIDER")
    print("=" * 60)
    print("\nSession summary:")
    print(json.dumps(summary, indent=2))

    print("\nClaim records (key fields):")
    with open(os.path.join(workspace, "session", "CLAIM_TABLE.substrate.json")) as f:
        table = json.load(f)
    for c in table.get("claims", []):
        print(f"\n  claim_id: {c['claim_id']}")
        print(f"  decision: {c['decision']}")
        print(f"  status:   {c['status']}")
        if "cross_substrate_evidence" in c:
            cse = c["cross_substrate_evidence"]
            print(f"  degrading at decision time: {len(cse['all_degrading'])}")
            for d in cse["all_degrading"]:
                print(f"    - {d['id']:20s} type={d['type']:18s} rate={d['rate']}")
            print(f"  upstream chosen: {cse['upstream_chosen']}")
        if c.get("source_matrix_row"):
            print(f"  source_matrix_row: {json.dumps(c['source_matrix_row'])}")
        if "validator" in c:
            v = c["validator"]
            errs = v.get("errors", {})
            for k, e in errs.items():
                print(f"    {k}: {e}")

    print("\nTraceability audit:")
    print(json.dumps(session.claim_table.audit_traceability(), indent=2))


if __name__ == "__main__":
    run_demo()
