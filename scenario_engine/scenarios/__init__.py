"""Deterministic event generators for the scenario engine.

Every scenario is a pure function of (class, seed, params, tick). Replaying
with the same inputs yields the same `ScenarioState` at the same tick.

`REGISTRY` maps `scenario.name` -> class so callers can look up scenarios by
string (used by the Session orchestrator).
"""

from .base import (
    ComponentState,
    Scenario,
    ScenarioState,
    SensorReading,
)
from .cascade_events import (
    SharedSubstrateFailure,
    SingleComponentThenPropagation,
    TimingDriftCascade,
)
from .environmental_events import (
    EMInterference,
    HumidityIntrusion,
    RadiationBurst,
)
from .mechanical_events import (
    FatigueCycling,
    ImpactShock,
    VibrationResonance,
)
from .power_events import Brownout, GroundLoop, VoltageSag
from .sustained_drift import SustainedDrift
from .thermal_events import (
    AmbientDrift,
    HeatSpikeLocalized,
    ThermalRunawayCascade,
)


_ALL_SCENARIOS = (
    HeatSpikeLocalized,
    AmbientDrift,
    ThermalRunawayCascade,
    VoltageSag,
    Brownout,
    GroundLoop,
    VibrationResonance,
    ImpactShock,
    FatigueCycling,
    SingleComponentThenPropagation,
    SharedSubstrateFailure,
    TimingDriftCascade,
    HumidityIntrusion,
    EMInterference,
    RadiationBurst,
    SustainedDrift,
)

REGISTRY = {cls.name: cls for cls in _ALL_SCENARIOS}


__all__ = [
    "Scenario",
    "SensorReading",
    "ComponentState",
    "ScenarioState",
    "REGISTRY",
    "HeatSpikeLocalized",
    "AmbientDrift",
    "ThermalRunawayCascade",
    "VoltageSag",
    "Brownout",
    "GroundLoop",
    "VibrationResonance",
    "ImpactShock",
    "FatigueCycling",
    "SingleComponentThenPropagation",
    "SharedSubstrateFailure",
    "TimingDriftCascade",
    "HumidityIntrusion",
    "EMInterference",
    "RadiationBurst",
    "SustainedDrift",
]
