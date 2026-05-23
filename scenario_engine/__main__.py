"""Demo: run a scenario, file a falsifiable claim, validate it.

  python -m scenario_engine
"""

import os
import sys
import tempfile

from scenario_engine.claims import ClaimRejected, ClaimWriter
from scenario_engine.runner import ScenarioRunner
from scenario_engine.scenarios.thermal_events import HeatSpikeLocalized
from scenario_engine.validators import OutcomeChecker


def main() -> int:
    scenario = HeatSpikeLocalized(seed=42)
    out_dir = tempfile.mkdtemp(prefix="scenario_engine_demo_")
    claim_path = os.path.join(out_dir, "CLAIM_TABLE.substrate.json")

    runner = ScenarioRunner(scenario, write_dir=out_dir)
    runner.run()

    writer = ClaimWriter(claim_path)

    # File a correct claim: target tick 130 (after fail at tick 120).
    target_tick = 130
    state_at_target = runner.state_at_tick(target_tick)
    actual_temp = state_at_target.actual_outcome["measurements"]["Q1_temp_c"]
    writer.file_claim(
        tick=80,
        event_detected="Q1_thermal_ramp",
        decision="prepare_repurpose_to_Q2",
        reasoning="Linear extrapolation crosses T_max around tick 120.",
        prediction={
            f"Q1_temp_c_at_tick_{target_tick}": actual_temp,
            f"system_state_at_tick_{target_tick}": "failed",
            "tolerance": 2.0,
        },
        scenario_id=scenario.name,
        seed=scenario.seed,
    )

    # File an intentionally wrong claim for contrast.
    writer.file_claim(
        tick=80,
        event_detected="Q1_thermal_ramp",
        decision="ignore",
        reasoning="(wrong) assume transient",
        prediction={
            f"Q1_temp_c_at_tick_{target_tick}": 25.0,
            f"system_state_at_tick_{target_tick}": "stable",
            "tolerance": 1.0,
        },
        scenario_id=scenario.name,
        seed=scenario.seed,
    )

    # Reject a non-falsifiable claim.
    try:
        writer.file_claim(
            tick=0,
            event_detected="vibes",
            decision="ignore",
            reasoning="hunch",
            prediction={"will_break_eventually": True},
        )
    except ClaimRejected as e:
        print(f"[rejected] vibes claim → {e}")

    # Grade everything.
    checker = OutcomeChecker(runner.states)
    for c in writer.claims():
        v = checker.evaluate_one(c)
        writer.update_status(c.claim_id, v.status, v.to_dict())
        print(f"{c.claim_id}  {v.status:<12}  margins={v.error_margins}")

    print(f"\nArtifacts written to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
