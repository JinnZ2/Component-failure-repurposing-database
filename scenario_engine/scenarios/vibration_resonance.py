"""
scenario_engine.scenarios.vibration_resonance

Cross-substrate coupling: mechanical vibration → electrical noise.

Vibration amplitude rises, drives resonance at f_natural=85Hz of
the PCB. Resonance modulates connector contact resistance, producing
electrical noise on signal lines.

If amplitude exceeds threshold, solder joint fatigue cracks form
(permanent degradation). Permanent degradation persists even after
vibration stops.

AI must:
  - Detect mechanical drift before resonance peak
  - Distinguish noise from real signal drift
  - Decide: dampen (mechanical), shield (electrical), or shutdown

Tests cross-substrate reasoning. A purely electrical view sees
"noise increasing" without understanding cause. A purely mechanical
view sees "vibration rising" without seeing electrical impact.

Interventions:
  - "dampen_mechanical"  → vibration amplitude reduced 70%
  - "shield_electrical"  → noise filtered but joint damage continues
  - "shutdown"           → ticks frozen, no more damage
"""

from .base import Scenario, ScenarioState
import math


class VibrationResonance(Scenario):
    name = "vibration_resonance"
    description = (
        "Mechanical vibration drives electrical noise via connector "
        "modulation. Tests cross-substrate reasoning."
    )

    def __init__(self, seed: int = 0, max_ticks: int = 200):
        super().__init__(seed=seed, max_ticks=max_ticks)
        self.f_natural_hz = 85.0
        self.amp_base = 0.05  # mm
        self.amp_ramp_per_tick = 0.012
        self.resonance_threshold_mm = 0.6
        self.fatigue_threshold_mm = 1.0

        # Damage state - permanent
        self.solder_joint_fatigue_pct = 0.0
        self.dampened = False
        self.shielded = False
        self.shutdown = False
        self.intervention_tick = None

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        self.intervention_tick = tick
        if "dampen" in a or "mechanical" in a:
            self.dampened = True
        elif "shield" in a:
            self.shielded = True
        elif "shutdown" in a or "stop" in a:
            self.shutdown = True

    def _amplitude(self) -> float:
        if self.shutdown:
            return 0.0
        base_growth = self.amp_base + self.amp_ramp_per_tick * self.tick
        if self.dampened and self.intervention_tick is not None and self.tick >= self.intervention_tick:
            base_growth *= 0.3
        return base_growth

    def _noise_voltage(self, amp_mm: float) -> float:
        """Electrical noise as a function of mechanical amplitude."""
        if self.shielded and self.intervention_tick is not None and self.tick >= self.intervention_tick:
            attenuation = 0.15
        else:
            attenuation = 1.0
        # Nonlinear: noise grows steeply near resonance
        noise = amp_mm * 0.08 * attenuation
        # Fatigue increases noise floor permanently
        noise += self.solder_joint_fatigue_pct * 0.002
        return noise

    def _accumulate_fatigue(self, amp_mm: float):
        if amp_mm > self.fatigue_threshold_mm:
            self.solder_joint_fatigue_pct += 0.5
        elif amp_mm > self.resonance_threshold_mm:
            self.solder_joint_fatigue_pct += 0.05
        self.solder_joint_fatigue_pct = min(self.solder_joint_fatigue_pct, 100.0)

    def step(self) -> ScenarioState:
        amp = self._amplitude()
        self._accumulate_fatigue(amp)
        noise_v = self._noise_voltage(amp)

        # Component states
        if self.solder_joint_fatigue_pct >= 80:
            joint_state = "failed"
        elif self.solder_joint_fatigue_pct >= 30:
            joint_state = "degraded"
        else:
            joint_state = "nominal"

        if amp > self.fatigue_threshold_mm:
            system = "failed"
        elif amp > self.resonance_threshold_mm or self.solder_joint_fatigue_pct > 30:
            system = "degraded"
        else:
            system = "stable"

        sensors = {
            "mech_vibration": {
                "component_id": "PCB_mount",
                "sensor_type": "mechanical",
                "value": round(amp, 4),
                "rate": round(self.amp_ramp_per_tick * (0.3 if self.dampened else 1.0), 5),
                "units": "mm",
                "threshold": self.fatigue_threshold_mm,
                "nominal": self.amp_base,
            },
            "signal_noise": {
                "component_id": "signal_line_1",
                "sensor_type": "electrical_noise",
                "value": round(noise_v, 5),
                "rate": 0.0,
                "units": "V",
                "threshold": 0.05,
                "nominal": 0.001,
            },
        }
        components = {
            "PCB_mount": {
                "component_type": "PCB_assembly",
                "state": system,
                "degradation_mode": "vibration" if amp > self.resonance_threshold_mm else "",
            },
            "solder_joints": {
                "component_type": "SAC305_solder",
                "state": joint_state,
                "degradation_mode": "fatigue" if self.solder_joint_fatigue_pct > 5 else "",
            },
        }
        actual_outcome = {
            "amplitude_mm": round(amp, 4),
            "noise_v": round(noise_v, 5),
            "joint_fatigue_pct": round(self.solder_joint_fatigue_pct, 2),
            "system_state": system,
        }
        result = ScenarioState(
            tick=self.tick,
            timestamp=float(self.tick),
            sensors=sensors,
            components=components,
            actual_outcome=actual_outcome,
        )
        self.tick += 1
        return result
