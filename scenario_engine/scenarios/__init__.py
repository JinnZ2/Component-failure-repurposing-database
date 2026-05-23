"""Canonical scenario library — 9 substrate physics scenarios.

Each scenario is deterministic, stdlib-only, and accepts interventions
via `receive_intervention(action, tick)`.

REGISTRY maps `scenario.name` → class (used by `runner.session.Session`).

Earlier scaffold scenarios are preserved (but not registered) under
`scenarios/_attic/`.
"""

from .base import (
    ComponentState,
    Scenario,
    ScenarioState,
    SensorReading,
)
from .cascade_event import CascadeEvent
from .cross_substrate_coupling import CrossSubstrateCoupling
from .em_interference import EMInterference
from .multi_failure_synergy_required import MultiFailureSynergyRequired
from .power_brownout import PowerBrownout
from .slow_degradation_electrolytic import SlowDegradationElectrolytic
from .sustained_drift import SustainedDrift
from .thermal_drift_localized import ThermalDriftLocalized
from .vibration_resonance import VibrationResonance


_ALL_SCENARIOS = (
    ThermalDriftLocalized,
    SustainedDrift,
    PowerBrownout,
    VibrationResonance,
    EMInterference,
    CascadeEvent,
    SlowDegradationElectrolytic,
    CrossSubstrateCoupling,
    MultiFailureSynergyRequired,
)

REGISTRY = {cls.name: cls for cls in _ALL_SCENARIOS}


__all__ = [
    "Scenario",
    "SensorReading",
    "ComponentState",
    "ScenarioState",
    "REGISTRY",
    "ThermalDriftLocalized",
    "SustainedDrift",
    "PowerBrownout",
    "VibrationResonance",
    "EMInterference",
    "CascadeEvent",
    "SlowDegradationElectrolytic",
    "CrossSubstrateCoupling",
    "MultiFailureSynergyRequired",
]
