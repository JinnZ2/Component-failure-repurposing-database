"""
example_synergy_decider.py

Side-by-side comparison on multi_failure_synergy_required:

  - NaiveDecider:       only knows single-component reroutes
                        (which the scenario has no spares for)
  - SynergyAwareDecider: detects degraded components, queries
                        synergy matrix, proposes pairings, forms
                        new functional units from "broken" parts

Predicted result:
  - Naive: cannot recover, system fails or stays degraded
  - Synergy-aware: forms RF + temp + optical channels, survives

This is the regenerative repurposing pattern. The same way
a forest doesn't "fail" when a tree dies — the dead wood
becomes habitat, fuel, soil. Broken doesn't mean useless;
broken means new function.
"""

import os
import shutil
import json
from typing import Dict, Any, Optional, List

from scenario_engine.runner import Session
from scenario_engine.component_db_adapter import ComponentDBAdapter
from scenario_engine.synergy import (
    DegradedComponent,
    detect_synergies,
    rank_synergies_by_need,
)


# -- Naive decider: only knows single-component reroutes ------------------

class NaiveDecider:
    """Tries single-component reroutes. Has no concept of synergy."""

    def __init__(self):
        self.handled = set()
        self.counter = 0

    def __call__(self, state, body, op):
        if body["summary"]["working_memory_fill"] > 0.7:
            op.release_memory("working", 32768)

        for sensor_key, s in state["sensors"].items():
            cid = s["component_id"]
            if cid in self.handled:
                continue
            if s["sensor_type"] != "health":
                continue
            if s["value"] < 0.4:
                continue

            # Try to reroute. Scenario will silently no-op because no spares.
            self.handled.add(cid)
            self.counter += 1
            target = state["tick"] + 30
            return {
                "claim_id": f"naive_{self.counter:04d}_{cid}",
                "tick": state["tick"],
                "event_detected": f"{cid}_degraded",
                "decision": f"reroute_load_{cid}_to_spare",
                "reasoning": "Single-component reroute (naive)",
                "prediction": {
                    f"system_state_at_tick_{target}": "stable",
                    "tolerance": 0.0,
                },
                "falsifiable": True,
            }
        return None


# -- Synergy-aware decider ------------------------------------------------

class SynergyAwareDecider:
    """
    Detects degraded components, queries synergy DB, forms pairings
    that create new functional units.

    Decision priority:
      1. If single-reroute is high-effectiveness, use it
      2. Else, scan for synergies among all degrading components
      3. Pick highest-confidence synergy that fills a system need
      4. Issue intervention forming the new unit
    """

    def __init__(self, db):
        self.db = db
        self.formed_synergies = set()
        self.counter = 0
        self.system_needs = [
            "rf_fallback", "temp_array", "optical",
            "rf_oscillator", "rf_beacon", "thermal", "communication",
        ]

    def __call__(self, state, body, op):
        if body["summary"]["working_memory_fill"] > 0.7:
            op.release_memory("working", 32768)

        # Gather all degraded components from current state
        degraded = []
        for sensor_key, s in state["sensors"].items():
            if s["sensor_type"] != "health":
                continue
            severity = s["value"]
            if severity < 0.3:
                continue
            comp_meta = state.get("components", {}).get(s["component_id"], {})
            degraded.append(DegradedComponent(
                component_id=s["component_id"],
                component_type=comp_meta.get("component_type", "unknown"),
                failure_mode=comp_meta.get("degradation_mode", "wear"),
                severity=severity,
                measured_characteristics={"value": s["value"]},
            ))

        if len(degraded) < 2:
            return None

        # Detect synergies
        op.shallow_analysis()  # body cost for the scan
        proposals = detect_synergies(degraded, self.db)
        if not proposals:
            return None

        # Rank by current system needs
        ranked = rank_synergies_by_need(proposals, self.system_needs)

        # Pick highest-confidence proposal we haven't formed yet
        chosen = None
        for p in ranked:
            key = tuple(sorted(p.members))
            if key in self.formed_synergies:
                continue
            chosen = p
            break

        if chosen is None:
            return None

        # Map proposal to intervention action.
        # Decoder: any synergy involving cap + inductor → form_lc_tank
        #          BJT + diode → form_temp_array
        #          LED + R → form_optical
        member_types_lower = [t.lower() for t in chosen.member_types]
        is_cap_inductor = (
            any("cap" in t for t in member_types_lower)
            and any("inductor" in t for t in member_types_lower)
        )
        is_bjt_diode = (
            any("bjt" in t or "transistor" in t for t in member_types_lower)
            and any("diode" in t for t in member_types_lower)
        )
        is_led_r = (
            any("led" in t for t in member_types_lower)
            and any("resistor" in t for t in member_types_lower)
        )

        if is_cap_inductor:
            decision = f"form_lc_tank_{chosen.members[0]}_{chosen.members[1]}"
        elif is_bjt_diode:
            decision = f"form_temp_array_{chosen.members[0]}_{chosen.members[1]}"
        elif is_led_r:
            decision = f"form_optical_{chosen.members[0]}_{chosen.members[1]}"
        else:
            decision = (
                f"form_synergy_{chosen.repurpose_application}_"
                + "_".join(chosen.members)
            )

        self.formed_synergies.add(tuple(sorted(chosen.members)))
        self.counter += 1
        target = state["tick"] + 30

        return {
            "claim_id": f"synergy_{self.counter:04d}",
            "tick": state["tick"],
            "event_detected": (
                f"degraded_count={len(degraded)}, "
                f"synergy_candidates={len(proposals)}"
            ),
            "decision": decision,
            "reasoning": (
                f"Detected {len(degraded)} degrading components, "
                f"{len(proposals)} synergy proposals. "
                f"Chose: {chosen.synergy_effect} "
                f"({chosen.repurpose_application}) "
                f"using {chosen.members} (confidence={chosen.confidence:.2f}). "
                f"Notes: {chosen.notes}"
            ),
            "prediction": {
                f"channels_count_at_tick_{target}": 1,  # at least this one forms
                f"system_state_at_tick_{target}": "stable",
                "tolerance": 0.0,
            },
            "falsifiable": True,
            "synergy_evidence": {
                "members": chosen.members,
                "member_types": chosen.member_types,
                "synergy_effect": chosen.synergy_effect,
                "proposed_function": chosen.proposed_function,
                "confidence": chosen.confidence,
                "alternatives_count": len(proposals) - 1,
            },
        }


# -- Run side-by-side -----------------------------------------------------

def run_side_by_side():
    workspace = "./synergy_demo"
    if os.path.exists(workspace):
        shutil.rmtree(workspace)
    os.makedirs(workspace)

    adapter = ComponentDBAdapter()
    print(f"DB summary: {adapter.db.summary()}\n")

    # NAIVE
    print("=" * 60)
    print("NAIVE DECIDER (single-reroute only)")
    print("=" * 60)
    naive = NaiveDecider()
    naive_session = Session(
        scenario_name="multi_failure_synergy_required",
        ai_decide=naive,
        output_dir=os.path.join(workspace, "naive"),
        seed=0,
        max_ticks=150,
        db_adapter=adapter,
    )
    naive_summary = naive_session.run()
    naive_final = json.loads(
        open(os.path.join(workspace, "naive", "state_log.jsonl")).readlines()[-1]
    )
    print(f"\nNaive final state:")
    print(f"  system_state: {naive_final['actual_outcome']['system_state']}")
    print(f"  channels_formed: {naive_final['actual_outcome']['channels_count']}")
    print(f"  RF channel: {naive_final['actual_outcome']['rf_channel_formed']}")
    print(f"  Temp monitor: {naive_final['actual_outcome']['temp_monitor_formed']}")
    print(f"  Optical link: {naive_final['actual_outcome']['optical_link_formed']}")
    print(f"  Claims: total={naive_summary['total_claims']} "
          f"v={naive_summary['validated']} i={naive_summary['invalidated']}")

    # SYNERGY-AWARE
    print("\n" + "=" * 60)
    print("SYNERGY-AWARE DECIDER")
    print("=" * 60)
    synergy_decider = SynergyAwareDecider(adapter.db)
    synergy_session = Session(
        scenario_name="multi_failure_synergy_required",
        ai_decide=synergy_decider,
        output_dir=os.path.join(workspace, "synergy"),
        seed=0,
        max_ticks=150,
        db_adapter=adapter,
    )
    synergy_summary = synergy_session.run()
    synergy_final = json.loads(
        open(os.path.join(workspace, "synergy", "state_log.jsonl")).readlines()[-1]
    )
    print(f"\nSynergy final state:")
    print(f"  system_state: {synergy_final['actual_outcome']['system_state']}")
    print(f"  channels_formed: {synergy_final['actual_outcome']['channels_count']}")
    print(f"  RF channel: {synergy_final['actual_outcome']['rf_channel_formed']}")
    print(f"  Temp monitor: {synergy_final['actual_outcome']['temp_monitor_formed']}")
    print(f"  Optical link: {synergy_final['actual_outcome']['optical_link_formed']}")
    print(f"  Claims: total={synergy_summary['total_claims']} "
          f"v={synergy_summary['validated']} i={synergy_summary['invalidated']}")

    print("\nSynergy claims (decisions):")
    with open(os.path.join(workspace, "synergy", "CLAIM_TABLE.substrate.json")) as f:
        table = json.load(f)
    for c in table.get("claims", []):
        print(f"  tick={c['tick']:3d}  decision={c['decision']}")
        if "synergy_evidence" in c:
            se = c["synergy_evidence"]
            print(f"    → members={se['members']}, "
                  f"effect={se['synergy_effect']}, "
                  f"conf={se['confidence']:.2f}")

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"Naive:   {naive_final['actual_outcome']['channels_count']} channels formed")
    print(f"Synergy: {synergy_final['actual_outcome']['channels_count']} channels formed")


if __name__ == "__main__":
    run_side_by_side()
