"""
scenario_engine.scenarios.base

Base class for all scenarios. A scenario is a deterministic
event generator that writes sensor state at each tick.

Python stdlib only.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass
class SensorReading:
    component_id: str
    sensor_type: str  # thermal | power | mechanical | em
    value: float
    rate: float  # dValue/dt
    units: str
    threshold: float
    nominal: float


@dataclass
class ComponentState:
    component_id: str
    component_type: str
    state: str  # nominal | degraded | failed
    degradation_mode: str = ""  # e.g. ESR_drift, beta_loss, leakage


@dataclass
class ScenarioState:
    tick: int
    timestamp: float
    sensors: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    components: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    actual_outcome: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "timestamp": self.timestamp,
            "sensors": self.sensors,
            "components": self.components,
            "actual_outcome": self.actual_outcome,
        }


class Scenario:
    """
    Base scenario. Subclass and implement step().

    A scenario must be deterministic: given the same seed and tick,
    it must produce the same state. No randomness without explicit seed.
    """

    name = "base"
    description = "abstract base"

    def __init__(self, seed: int = 0, max_ticks: int = 1000):
        self.seed = seed
        self.max_ticks = max_ticks
        self.tick = 0
        self.history = []

    def step(self) -> ScenarioState:
        """
        Advance one tick. Return ScenarioState.
        Subclass must implement.
        """
        raise NotImplementedError

    def reset(self):
        self.tick = 0
        self.history = []

    def write_state(self, state: ScenarioState, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(state.to_dict(), f, indent=2)
        self.history.append(state)
