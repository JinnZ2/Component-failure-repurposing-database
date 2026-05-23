"""Shared helpers for scenarios.

Deterministic noise, sensor/component packaging, and tick<->time conversion.
Stdlib only.
"""

import hashlib
import math
import random
from dataclasses import asdict
from typing import Any, Dict

from .base import ComponentState, ScenarioState, SensorReading


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def make_rng(*parts: object) -> random.Random:
    """Build a `random.Random` from a stable hash of parts."""
    fp = "|".join(str(p) for p in parts).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(fp).digest()[:8], "big", signed=False)
    return random.Random(seed)


def gaussian(rng: random.Random, sigma: float) -> float:
    """Box-Muller Gaussian noise using a `random.Random`."""
    if sigma <= 0:
        return 0.0
    u1 = max(1e-12, rng.random())
    u2 = rng.random()
    return sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


# ---------------------------------------------------------------------------
# ScenarioState packaging
# ---------------------------------------------------------------------------

def reading_dict(r: SensorReading) -> Dict[str, Any]:
    """asdict(SensorReading) — kept as a thin wrapper so callers don't import
    dataclasses just for serialisation."""
    return asdict(r)


def component_dict(c: ComponentState) -> Dict[str, Any]:
    return asdict(c)


def add_sensor(state: ScenarioState, reading: SensorReading) -> None:
    """Insert a reading into state.sensors[sensor_type][component_id]."""
    bucket = state.sensors.setdefault(reading.sensor_type, {})
    bucket[reading.component_id] = reading_dict(reading)


def add_component(state: ScenarioState, comp: ComponentState) -> None:
    state.components[comp.component_id] = component_dict(comp)


def add_measurement(state: ScenarioState, name: str, value: float) -> None:
    meas = state.actual_outcome.setdefault("measurements", {})
    meas[name] = value


def set_system_state(state: ScenarioState, label: str) -> None:
    state.actual_outcome["system_state"] = label


def add_failed(state: ScenarioState, component_id: str) -> None:
    failed = state.actual_outcome.setdefault("failed_components", [])
    if component_id not in failed:
        failed.append(component_id)


def add_event(state: ScenarioState, event: str) -> None:
    events = state.actual_outcome.setdefault("active_events", [])
    events.append(event)


# ---------------------------------------------------------------------------
# Tick <-> time
# ---------------------------------------------------------------------------

def tick_to_time(tick: int, dt: float) -> float:
    return round(tick * dt, 6)


def time_to_tick(t: float, dt: float) -> int:
    return int(round(t / dt))


# ---------------------------------------------------------------------------
# Component-state derivation
# ---------------------------------------------------------------------------

def comp(component_id: str, component_type: str, *,
         state: str = "nominal", degradation_mode: str = "") -> ComponentState:
    return ComponentState(
        component_id=component_id,
        component_type=component_type,
        state=state,
        degradation_mode=degradation_mode,
    )


def reading(component_id: str, sensor_type: str, *,
            value: float, rate: float, units: str,
            threshold: float, nominal: float) -> SensorReading:
    return SensorReading(
        component_id=component_id,
        sensor_type=sensor_type,
        value=value,
        rate=rate,
        units=units,
        threshold=threshold,
        nominal=nominal,
    )


__all__ = [
    "make_rng",
    "gaussian",
    "reading_dict",
    "component_dict",
    "add_sensor",
    "add_component",
    "add_measurement",
    "set_system_state",
    "add_failed",
    "add_event",
    "tick_to_time",
    "time_to_tick",
    "comp",
    "reading",
]
