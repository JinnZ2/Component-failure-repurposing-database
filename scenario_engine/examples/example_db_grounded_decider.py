"""
example_db_grounded_decider.py

Decider that queries the wired-in component DB to choose
intervention based on actual repurpose effectiveness data
from the CSV matrices.

Contrast with prior deciders that hard-coded "reroute_load_X_to_spare"
strings — this one ASKS the DB what to do, gets a ranked list, and
picks the highest-effectiveness option for the specific component+failure.

Pipeline per tick:
  1. Read sensor (body op)
  2. Detect failure mode from sensor reading
  3. Query component DB with (component_type, failure_mode)
  4. Receive structured response: best intervention, alternatives,
     environmental modifiers
  5. Issue claim with DB-grounded decision and effectiveness score
"""

import os
import shutil
import json
from typing import Dict, Any, Optional

from scenario_engine.runner import Session
from scenario_engine.component_db_adapter import ComponentDBAdapter


# Map from sensor types to component types in the DB
SENSOR_TO_COMPONENT = {
    "thermal":   ("BJT_NPN", "thermal_runaway"),
    "esr":       ("electrolytic_cap", "ESR_drift"),
    "mechanical": ("PCB_assembly", "vibration_fatigue"),
    "signal":    ("signal_trace", "real_drift"),
}


class DBGroundedDecider:
    def __init__(self):
        self.handled = set()
        self.counter = 0
        # Cache of DB queries this session (avoids repeated lookups)
        self._db_cache = {}

    def __call__(self, state, body, op):
        # Body management
        if body["summary"]["working_memory_fill"] > 0.7:
            op.release_memory("working", 32768)

        for sensor_key, s in state["sensors"].items():
            stype = s["sensor_type"]
            cid = s["component_id"]
            key = (cid, stype)
            if key in self.handled:
                continue

            # Detection: deviation, rate, or threshold proximity
            deviation = (
                abs(s["value"] - s["nominal"]) / abs(s["nominal"])
                if s["nominal"] != 0 else 0.0
            )
            rate_signal = s["rate"] > 0.3
            threshold_close = (
                s["value"] >= s["threshold"] * 0.7
                if s["threshold"] > 0 else False
            )
            if not (deviation > 0.15 or rate_signal or threshold_close):
                continue

            # Map to DB component
            db_lookup = SENSOR_TO_COMPONENT.get(stype)
            if db_lookup is None:
                continue
            component_type, failure_mode = db_lookup

            # Query the DB through the wired-in adapter
            cache_key = f"{component_type}_{failure_mode}"
            db_result = op.query_component_db(
                cache_key=cache_key,
                component_type=component_type,
                failure_mode=failure_mode,
                include=["best", "repurpose_options", "environmental"],
            )

            if not db_result.get("success"):
                continue

            db = db_result.get("db", {})
            best = db.get("best")
            options = db.get("repurpose_options", [])

            if not best:
                # No intervention in DB for this failure mode
                continue

            # Decide based on DB recommendation
            intervention_name = best["repurpose_option"]
            effectiveness = best["effectiveness"]
            effectiveness_score = best["effectiveness_score"]

            # Translate the DB's intervention name into the scenario's
            # intervention vocabulary. The scenario accepts substring matches,
            # so we pass the DB name through.
            decision = intervention_name

            # Compute analysis depth based on body
            compute_headroom = (
                body["compute"]["cycles_per_tick"]
                - body["compute"]["cycles_used_this_tick"]
            )
            if body["throttled"] or compute_headroom < 2500:
                op.shallow_analysis()
                tol = 10.0
            else:
                op.deep_analysis()
                tol = 5.0

            self.handled.add(key)
            self.counter += 1
            target = state["tick"] + 30

            # Adjust prediction confidence based on DB effectiveness
            # Higher effectiveness → tighter tolerance
            tol *= (1.5 - effectiveness_score)

            return {
                "claim_id": f"dbg_{self.counter:04d}_{cid}",
                "tick": state["tick"],
                "event_detected": (
                    f"{stype}_drift_{cid} "
                    f"(deviation={deviation:.2f}, rate={s['rate']})"
                ),
                "decision": decision,
                "reasoning": (
                    f"DB lookup: component={component_type}, "
                    f"failure_mode={failure_mode}, "
                    f"recommended={intervention_name}, "
                    f"effectiveness={effectiveness} "
                    f"(score={effectiveness_score}). "
                    f"Notes: {best.get('notes', '')}. "
                    f"Alternatives in DB: {len(options) - 1}."
                ),
                "prediction": {
                    f"system_state_at_tick_{target}": "stable",
                    "tolerance": tol,
                },
                "falsifiable": True,
                "db_grounded": True,
                # Audit trail: link this decision back to the exact CSV row.
                "source_matrix_row": best.get("source_matrix_row"),
                "db_evidence": {
                    "component": component_type,
                    "failure_mode": failure_mode,
                    "intervention": intervention_name,
                    "effectiveness_score": effectiveness_score,
                    "alternatives_count": max(0, len(options) - 1),
                },
            }
        return None


def run_demo():
    workspace = "./db_grounded_demo"
    if os.path.exists(workspace):
        shutil.rmtree(workspace)
    os.makedirs(workspace, exist_ok=True)

    # Initialize adapter with bundled sample data
    adapter = ComponentDBAdapter()
    print(f"DB summary: {adapter.db.summary()}\n")

    # Demonstrate raw DB capabilities
    print("=" * 60)
    print("RAW DB QUERIES (before running session)")
    print("=" * 60)

    print("\nrepurpose_options(BJT_NPN, thermal_runaway):")
    for opt in adapter.db.repurpose_options("BJT_NPN", "thermal_runaway"):
        print(f"  - {opt['repurpose_option']:30s} "
              f"effectiveness={opt['effectiveness']:6s} "
              f"score={opt['effectiveness_score']}")

    print("\nbest_intervention(electrolytic_cap, ESR_drift):")
    b = adapter.db.best_intervention("electrolytic_cap", "ESR_drift")
    print(f"  {b['repurpose_option']} (eff={b['effectiveness']})")

    print("\nenvironmental_factors(electrolytic_cap, 'humidity'):")
    for ef in adapter.db.environmental_factors("electrolytic_cap", "humidity"):
        print(f"  {ef['condition']} → {ef['observed_effect']}")

    print("\nsynergies('failed_diode'):")
    for s in adapter.db.synergies("failed_diode"):
        print(f"  {s['component_a']} + {s['component_b']} → {s['synergy_effect']}")

    # Now run a session using the adapter
    print("\n\n" + "=" * 60)
    print("SESSION WITH DB-GROUNDED DECIDER")
    print("=" * 60)

    decider = DBGroundedDecider()
    session = Session(
        scenario_name="thermal_drift_localized",
        ai_decide=decider,
        output_dir=os.path.join(workspace, "session"),
        seed=0,
        max_ticks=200,
        external_thermal_coupling=0.0,
        db_adapter=adapter,
    )
    summary = session.run()
    print("\nSession summary:")
    print(json.dumps(summary, indent=2))

    print("\nClaim record:")
    with open(os.path.join(workspace, "session", "CLAIM_TABLE.substrate.json")) as f:
        table = json.load(f)
    for c in table.get("claims", []):
        print(f"\n  claim_id: {c['claim_id']}")
        print(f"  decision: {c['decision']}")
        print(f"  status:   {c['status']}")
        if c.get("source_matrix_row"):
            print(f"  source_matrix_row: {json.dumps(c['source_matrix_row'])}")
        if "db_evidence" in c:
            print(f"  db_evidence: {json.dumps(c['db_evidence'], indent=4)}")

    # Traceability audit: every decision should trace back to a CSV row.
    print("\nTraceability audit:")
    print(json.dumps(session.claim_table.audit_traceability(), indent=2))


if __name__ == "__main__":
    run_demo()
