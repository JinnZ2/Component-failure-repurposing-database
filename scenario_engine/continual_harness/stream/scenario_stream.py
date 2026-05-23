"""
scenario_engine.continual_harness.stream.scenario_stream

Generates a sequence of scenarios with controlled variation.

A stream is a list of (scenario_name, seed, max_ticks, kwargs) tuples.
Determinism: same stream definition produces same sequence.

Patterns:
  - repeated:   same scenario N times, vary seed, watch accuracy converge
  - mixed:      cycle through several scenarios
  - curriculum: easy → hard progression
  - shuffled:   randomized but reproducible
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Iterator, Optional


@dataclass
class ScenarioSpec:
    scenario_name: str
    seed: int
    max_ticks: int
    session_id: str
    kwargs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "scenario_name": self.scenario_name,
            "seed": self.seed,
            "max_ticks": self.max_ticks,
            "session_id": self.session_id,
            "kwargs": self.kwargs,
        }


class ScenarioStream:
    """Iterable sequence of ScenarioSpec."""

    def __init__(self, specs: List[ScenarioSpec]):
        self.specs = specs

    def __iter__(self) -> Iterator[ScenarioSpec]:
        return iter(self.specs)

    def __len__(self):
        return len(self.specs)

    def __getitem__(self, idx):
        return self.specs[idx]


def repeated(
    scenario_name: str,
    n: int,
    max_ticks: int = 200,
    base_seed: int = 0,
) -> ScenarioStream:
    """Same scenario N times, varying seed."""
    specs = []
    for i in range(n):
        specs.append(ScenarioSpec(
            scenario_name=scenario_name,
            seed=base_seed + i,
            max_ticks=max_ticks,
            session_id=f"{scenario_name}_rep_{i:04d}",
        ))
    return ScenarioStream(specs)


def mixed(
    scenarios: List[str],
    cycles: int,
    max_ticks: int = 200,
    base_seed: int = 0,
) -> ScenarioStream:
    """Cycle through scenarios."""
    specs = []
    idx = 0
    for c in range(cycles):
        for s in scenarios:
            specs.append(ScenarioSpec(
                scenario_name=s,
                seed=base_seed + idx,
                max_ticks=max_ticks,
                session_id=f"mixed_{idx:04d}_{s}",
            ))
            idx += 1
    return ScenarioStream(specs)


def shuffled(
    scenarios: List[str],
    n: int,
    max_ticks: int = 200,
    base_seed: int = 0,
    shuffle_seed: int = 42,
) -> ScenarioStream:
    """Randomized order, reproducible via shuffle_seed."""
    rng = random.Random(shuffle_seed)
    specs = []
    for i in range(n):
        s = rng.choice(scenarios)
        specs.append(ScenarioSpec(
            scenario_name=s,
            seed=base_seed + i,
            max_ticks=max_ticks,
            session_id=f"shuf_{i:04d}_{s}",
        ))
    return ScenarioStream(specs)


def curriculum(
    stages: List[Dict[str, Any]],
) -> ScenarioStream:
    """
    Multi-stage progression. Each stage spec:
      {
        "scenario_name": str,
        "count": int,
        "max_ticks": int,
        "base_seed": int,
      }

    Stage 1 runs to completion before stage 2 begins.
    """
    specs = []
    idx = 0
    for stage_num, stage in enumerate(stages):
        for i in range(stage["count"]):
            specs.append(ScenarioSpec(
                scenario_name=stage["scenario_name"],
                seed=stage.get("base_seed", 0) + i,
                max_ticks=stage.get("max_ticks", 200),
                session_id=f"stage{stage_num}_{idx:04d}_{stage['scenario_name']}",
                kwargs={"stage": stage_num},
            ))
            idx += 1
    return ScenarioStream(specs)
