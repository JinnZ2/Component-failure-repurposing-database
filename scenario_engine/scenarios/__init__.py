"""Deterministic event generators for the scenario engine.

Every scenario is a pure function of (class, seed, params, tick). Replaying
with the same inputs yields the same `ScenarioState` at the same tick.
"""

from .base import (
    ComponentState,
    Scenario,
    ScenarioState,
    SensorReading,
)

__all__ = ["Scenario", "SensorReading", "ComponentState", "ScenarioState"]
