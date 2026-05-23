"""
example_pattern_extraction.py

Multi-session run, then pattern extraction.

Runs the cross-substrate decider across 30 sessions on varied scenarios,
then extracts patterns showing:
  - Per-scenario accuracy breakdown
  - Per-decision validation rates
  - Numeric error distribution
  - Systematic bias in predictions
  - DB-effectiveness audit (claimed vs observed)
  - Recurring failure patterns
"""

import os
import shutil
import json

from scenario_engine.continual_harness import ContinualHarness
from scenario_engine.continual_harness.stream import mixed
from scenario_engine.continual_harness.feedback import extract_all_patterns
from scenario_engine.component_db_adapter import ComponentDBAdapter
from scenario_engine.examples.example_cross_substrate_decider import CrossSubstrateDecider


class HarnessAdapter:
    """Wraps the CrossSubstrateDecider for the harness signature."""

    def __init__(self):
        self._d = CrossSubstrateDecider()

    def __call__(self, state, body, op, history):
        return self._d(state, body, op)


def run():
    workspace = "./pattern_demo_workspace"
    if os.path.exists(workspace):
        shutil.rmtree(workspace)

    adapter = ComponentDBAdapter()

    stream = mixed(
        scenarios=[
            "thermal_drift_localized",
            "cross_substrate_coupling",
            "cascade_event",
        ],
        cycles=10,
        max_ticks=200,
    )
    harness = ContinualHarness(
        stream=stream,
        decider_factory=HarnessAdapter,
        workspace=workspace,
        external_thermal_coupling=0.5,
        wrap_decider_with_history=True,
        resume=False,
        db_adapter=adapter,
    )
    report = harness.run()

    print("=" * 60)
    print("HARNESS RUN COMPLETE")
    print("=" * 60)
    print(json.dumps({
        "overall": report["overall_accuracy"],
        "per_scenario": report["per_scenario"],
    }, indent=2))

    # Now extract patterns
    print("\n" + "=" * 60)
    print("PATTERN EXTRACTION")
    print("=" * 60)

    history_path = os.path.join(workspace, "claim_history.json")
    pattern_path = os.path.join(workspace, "PATTERN_TABLE.json")
    patterns = extract_all_patterns(history_path, output_path=pattern_path)

    print("\nBy-scenario accuracy:")
    for s, stats in patterns["by_scenario"].items():
        print(f"  {s:35s} acc={stats['accuracy']:.2f} "
              f"v={stats['validated']} i={stats['invalidated']} "
              f"p={stats['partial']}")

    print("\nBy-decision accuracy:")
    for d, stats in patterns["by_decision"].items():
        print(f"  {d:35s} acc={stats['accuracy']:.2f} n={stats['total']}")

    print("\nNumeric error distribution:")
    ned = patterns["numeric_error_distribution"]
    if ned:
        print(f"  n={ned['n']}, mean={ned['mean']:.2f}, "
              f"min={ned['min']:.2f}, max={ned['max']:.2f}, "
              f"stdev={ned['stdev']:.2f}")
    else:
        print("  (no numeric errors recorded)")

    print("\nDB effectiveness audit:")
    for entry in patterns["db_effectiveness_audit"]:
        print(f"  {entry['intervention']:30s} "
              f"db_score={entry['db_effectiveness_score']:.2f}  "
              f"observed_rate={entry['observed_validation_rate']:.2f}  "
              f"delta={entry['delta']:+.2f}  n={entry['samples']}")

    print("\nRecurring failure patterns:")
    if patterns["recurring_failures"]:
        for f in patterns["recurring_failures"]:
            print(f"  {f['scenario']:30s} → {f['decision']:30s} "
                  f"failed {f['failures']}/{f['attempts']}")
    else:
        print("  (none detected)")

    print(f"\nFull pattern report written to: {pattern_path}")


if __name__ == "__main__":
    run()
