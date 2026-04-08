"""
Component Degradation Simulation
=================================
Models time-series degradation of electronic components under configurable
stress profiles. Tracks drift from nominal values and flags repurposing
thresholds.

Covers:
  - Resistor value drift (carbon film aging)
  - Capacitor ESR rise (electrolytic dry-out)
  - Diode leakage increase (junction degradation)

Evidence tier: Theoretical (physics-based models, not yet lab-validated)

Reference:
  - binary_sensor.md — health scoring, drift % formula
  - components/resistors/carbon_film.md — drift characteristics
  - components/capacitors/electrolytic.md — ESR aging
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class ComponentType(Enum):
    RESISTOR = "resistor"
    CAPACITOR = "capacitor"
    DIODE = "diode"


class FailureMode(Enum):
    NONE = "none"
    DRIFT = "drift"
    DEGRADATION = "degradation"
    OPEN_CIRCUIT = "open_circuit"
    SHORT_CIRCUIT = "short_circuit"


@dataclass
class StressProfile:
    """Environmental stress applied each hour of operation."""
    temperature_c: float = 25.0     # ambient temperature
    humidity_pct: float = 50.0      # relative humidity
    voltage_ratio: float = 0.8      # applied / rated voltage
    vibration_g: float = 0.0        # mechanical vibration (g-force)


@dataclass
class DegradationSnapshot:
    hour: int
    value: float
    drift_pct: float
    health: float            # 0.0 (failed) to 1.0 (nominal)
    failure_mode: FailureMode
    repurpose_viable: bool


# ---------------------------------------------------------------------------
# Degradation models
# ---------------------------------------------------------------------------

def _health_score(drift_pct: float, warn_thresh: float = 5.0,
                  fail_thresh: float = 20.0) -> float:
    """Piecewise health score matching binary_sensor.md formula."""
    if drift_pct <= warn_thresh:
        return 1.0
    if drift_pct >= fail_thresh:
        return 0.0
    return 1.0 - (drift_pct - warn_thresh) / (fail_thresh - warn_thresh)


def _classify(drift_pct: float, warn: float = 5.0,
              fail: float = 20.0) -> FailureMode:
    if drift_pct < warn:
        return FailureMode.NONE
    if drift_pct < fail:
        return FailureMode.DRIFT
    return FailureMode.DEGRADATION


class ResistorDegradation:
    """
    Carbon-film resistor drift model.

    Resistance increases roughly logarithmically with time under thermal
    stress.  Arrhenius acceleration factor scales with temperature above
    a reference of 70 deg C.

        drift(t) = base_rate * ln(1 + t) * acceleration_factor + noise
    """

    def __init__(self, nominal_ohms: float = 10_000.0,
                 base_drift_rate: float = 0.002,
                 ref_temp_c: float = 70.0):
        self.nominal = nominal_ohms
        self.base_rate = base_drift_rate
        self.ref_temp = ref_temp_c

    def simulate(self, hours: int, stress: StressProfile,
                 step: int = 100) -> List[DegradationSnapshot]:
        snapshots: List[DegradationSnapshot] = []
        accel = math.exp(0.05 * max(0.0, stress.temperature_c - self.ref_temp))
        for h in range(0, hours + 1, step):
            drift_frac = self.base_rate * math.log1p(h) * accel
            noise = random.gauss(0, 0.001 * (1 + h / 5000))
            value = self.nominal * (1.0 + drift_frac + noise)
            drift_pct = abs(value - self.nominal) / self.nominal * 100
            health = _health_score(drift_pct)
            mode = _classify(drift_pct)
            repurpose = 0.0 < health < 0.7
            snapshots.append(DegradationSnapshot(
                hour=h, value=value, drift_pct=drift_pct,
                health=health, failure_mode=mode,
                repurpose_viable=repurpose,
            ))
        return snapshots


class CapacitorDegradation:
    """
    Electrolytic capacitor ESR rise model.

    ESR increases as electrolyte evaporates. Modeled as exponential growth
    accelerated by temperature (Arrhenius) and voltage stress.

        ESR(t) = ESR_0 * exp(growth_rate * t * accel)
    """

    def __init__(self, nominal_uf: float = 100.0,
                 initial_esr_ohms: float = 0.05,
                 growth_rate: float = 1e-5,
                 ref_temp_c: float = 85.0):
        self.nominal_uf = nominal_uf
        self.esr_0 = initial_esr_ohms
        self.growth_rate = growth_rate
        self.ref_temp = ref_temp_c

    def simulate(self, hours: int, stress: StressProfile,
                 step: int = 100) -> List[DegradationSnapshot]:
        snapshots: List[DegradationSnapshot] = []
        temp_accel = math.exp(0.04 * max(0.0, stress.temperature_c - self.ref_temp))
        volt_accel = 1.0 + 0.5 * max(0.0, stress.voltage_ratio - 0.8)
        accel = temp_accel * volt_accel
        for h in range(0, hours + 1, step):
            esr = self.esr_0 * math.exp(self.growth_rate * h * accel)
            noise = random.gauss(0, 0.002 * self.esr_0)
            esr = max(self.esr_0, esr + noise)
            drift_pct = (esr - self.esr_0) / self.esr_0 * 100
            health = _health_score(drift_pct, warn_thresh=20.0, fail_thresh=100.0)
            mode = _classify(drift_pct, warn=20.0, fail=100.0)
            repurpose = 0.0 < health < 0.7
            snapshots.append(DegradationSnapshot(
                hour=h, value=esr, drift_pct=drift_pct,
                health=health, failure_mode=mode,
                repurpose_viable=repurpose,
            ))
        return snapshots


class DiodeDegradation:
    """
    Silicon diode leakage current model.

    Reverse leakage grows with junction temperature and aging.  Modeled
    as a power-law increase with stochastic spikes representing
    micro-damage events.

        I_leak(t) = I_0 * (1 + k * t^0.7) * temp_factor
    """

    def __init__(self, nominal_leak_ua: float = 0.01,
                 aging_coeff: float = 5e-4,
                 ref_temp_c: float = 25.0):
        self.i0 = nominal_leak_ua
        self.k = aging_coeff
        self.ref_temp = ref_temp_c

    def simulate(self, hours: int, stress: StressProfile,
                 step: int = 100) -> List[DegradationSnapshot]:
        snapshots: List[DegradationSnapshot] = []
        temp_factor = 2.0 ** ((stress.temperature_c - self.ref_temp) / 10.0)
        for h in range(0, hours + 1, step):
            leak = self.i0 * (1.0 + self.k * (h ** 0.7)) * temp_factor
            if random.random() < 0.02:
                leak *= random.uniform(1.5, 3.0)
            drift_pct = (leak - self.i0) / self.i0 * 100
            health = _health_score(drift_pct, warn_thresh=50.0, fail_thresh=500.0)
            mode = _classify(drift_pct, warn=50.0, fail=500.0)
            repurpose = 0.0 < health < 0.7
            snapshots.append(DegradationSnapshot(
                hour=h, value=leak, drift_pct=drift_pct,
                health=health, failure_mode=mode,
                repurpose_viable=repurpose,
            ))
        return snapshots


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _print_timeline(label: str, unit: str,
                    snapshots: List[DegradationSnapshot]) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"{'=' * 70}")
    print(f"{'Hour':>8}  {'Value':>12}  {'Drift%':>8}  {'Health':>7}  "
          f"{'Mode':<14}  {'Repurpose?'}")
    print(f"{'-' * 8}  {'-' * 12}  {'-' * 8}  {'-' * 7}  "
          f"{'-' * 14}  {'-' * 10}")
    for s in snapshots:
        rp = "YES" if s.repurpose_viable else ""
        print(f"{s.hour:>8}  {s.value:>11.4f} {unit}  {s.drift_pct:>7.2f}%  "
              f"{s.health:>6.3f}  {s.failure_mode.value:<14}  {rp}")


def run() -> None:
    random.seed(42)
    hours = 10_000
    stress = StressProfile(temperature_c=85.0, humidity_pct=70.0,
                           voltage_ratio=0.9)

    print("Component Degradation Simulation")
    print(f"Duration: {hours:,} hours | Temp: {stress.temperature_c} deg C | "
          f"Humidity: {stress.humidity_pct}% | V ratio: {stress.voltage_ratio}")

    r = ResistorDegradation(nominal_ohms=10_000.0)
    _print_timeline("Resistor — 10 kOhm Carbon Film", "Ohm",
                    r.simulate(hours, stress))

    c = CapacitorDegradation(nominal_uf=100.0, initial_esr_ohms=0.05)
    _print_timeline("Capacitor — 100 uF Electrolytic (ESR)", "Ohm",
                    c.simulate(hours, stress))

    d = DiodeDegradation(nominal_leak_ua=0.01)
    _print_timeline("Diode — Silicon Junction (Leakage)", "uA",
                    d.simulate(hours, stress))


if __name__ == "__main__":
    run()
