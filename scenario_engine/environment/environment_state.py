"""
scenario_engine.environment.environment_state

Environmental conditions that affect failure rates AND synergy viability.

Two layers:
  1. Instantaneous conditions (current temp, humidity, vibration, contamination)
  2. Cumulative memory (thermal cycles, humidity-hours, vibration dose,
     contamination deposit) — damage that does not heal

Based on the EnvironmentalMemory spec from the
Component-failure-repurposing-database CLAUDE.md.

This module produces an acceleration_factor that scenarios use to
modulate component degradation rates, and produces validity gates
for synergy proposals (some pairings don't work above certain temps).

All values measurable. No subjective interpretation.
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional


@dataclass
class EnvironmentalMemory:
    """Cumulative damage that does not heal when conditions recover.

    Thermal cycle detection: peak-to-peak ΔT amplitude. A cycle counts
    whenever the running min/max temperature spread since the last cycle
    event exceeds `thermal_cycle_threshold_c` (default 20°C). This
    matches the Coffin-Manson model where solder fatigue is driven by
    ΔT amplitude, not by crossing any specific absolute temperature.
    """
    thermal_cycles: int = 0
    humidity_exposure_seconds: float = 0.0      # time above 70% RH
    vibration_dose: float = 0.0                 # integral of g^2 * dt
    contamination_deposit: float = 0.0          # 0-1, accumulates
    peak_high: Optional[float] = None           # running max since last cycle
    peak_low: Optional[float] = None            # running min since last cycle
    thermal_cycle_threshold_c: float = 20.0     # ΔT that triggers a cycle
    started_at: float = field(default_factory=time.time)

    def update(self, temp_c: float, humidity_pct: float,
               vibration_g: float, contamination: float, dt: float):
        # Peak-to-peak cycle detection
        if self.peak_high is None:
            # First observation seeds the peaks.
            self.peak_high = temp_c
            self.peak_low = temp_c
        else:
            if temp_c > self.peak_high:
                self.peak_high = temp_c
            if temp_c < self.peak_low:
                self.peak_low = temp_c
            if self.peak_high - self.peak_low >= self.thermal_cycle_threshold_c:
                self.thermal_cycles += 1
                # Reset peaks so the next equal-magnitude swing counts again.
                self.peak_high = temp_c
                self.peak_low = temp_c

        # Humidity exposure
        if humidity_pct > 70.0:
            self.humidity_exposure_seconds += dt

        # Vibration dose
        self.vibration_dose += vibration_g ** 2 * dt

        # Contamination deposit (saturates at 1.0)
        self.contamination_deposit = min(
            1.0, self.contamination_deposit + contamination * dt * 0.01
        )

    def to_dict(self):
        return asdict(self)


@dataclass
class EnvironmentState:
    """Current environmental conditions."""
    temp_c: float = 25.0
    humidity_pct: float = 50.0
    vibration_g: float = 0.1
    contamination: float = 0.0
    memory: EnvironmentalMemory = field(default_factory=EnvironmentalMemory)
    last_update: float = field(default_factory=time.time)

    def update(self, temp_c: Optional[float] = None,
               humidity_pct: Optional[float] = None,
               vibration_g: Optional[float] = None,
               contamination: Optional[float] = None,
               dt: Optional[float] = None):
        """
        Apply new instantaneous values. Memory updates using prior state.
        dt defaults to wall-clock since last update if not provided.
        """
        now = time.time()
        actual_dt = dt if dt is not None else (now - self.last_update)
        self.memory.update(
            self.temp_c, self.humidity_pct,
            self.vibration_g, self.contamination,
            actual_dt,
        )
        if temp_c is not None:
            self.temp_c = temp_c
        if humidity_pct is not None:
            self.humidity_pct = humidity_pct
        if vibration_g is not None:
            self.vibration_g = vibration_g
        if contamination is not None:
            self.contamination = contamination
        self.last_update = now

    def acceleration_factor(self, component_type: str = "generic",
                            failure_mode: str = "wear") -> float:
        """
        Multiplier for failure progression rate.
        Combines instantaneous + cumulative damage.

        Returns 1.0 in nominal conditions; higher under stress.
        """
        # Instantaneous factors
        inst = 1.0
        # Arrhenius (10°C doubles rate)
        inst *= 2 ** ((self.temp_c - 25.0) / 10.0)
        # Humidity above 70%
        if self.humidity_pct > 70.0:
            inst *= 1.0 + (self.humidity_pct - 70.0) / 30.0
        # Vibration linear
        inst *= 1.0 + self.vibration_g * 0.5
        # Contamination — connectors more sensitive
        if "connector" in component_type.lower():
            inst *= 1.0 + self.contamination * 5.0
        else:
            inst *= 1.0 + self.contamination * 2.0

        # Cumulative memory
        cum = 1.0
        cum *= 1.0 + self.memory.thermal_cycles * 0.02
        cum *= 1.0 + (self.memory.humidity_exposure_seconds / 3600.0) * 0.05
        cum *= 1.0 + self.memory.vibration_dose * 0.001
        cum *= 1.0 + self.memory.contamination_deposit

        return inst * cum

    def to_dict(self) -> Dict[str, Any]:
        return {
            "temp_c": self.temp_c,
            "humidity_pct": self.humidity_pct,
            "vibration_g": self.vibration_g,
            "contamination": self.contamination,
            "memory": self.memory.to_dict(),
            "acceleration_at_25C_nominal": round(
                self.acceleration_factor("generic"), 4
            ),
        }
