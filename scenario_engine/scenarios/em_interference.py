"""
scenario_engine.scenarios.em_interference

Two analog signal lines.
  - signal_A : real drift, monotonic and slow. Crosses a soft threshold
               unless the AI calibrates it. This IS a problem.
  - signal_B : EM noise bursts (periodic, bipolar, transient). Each burst
               lasts a few ticks and then disappears completely. This is
               NOT a problem — it's external interference.

The AI must distinguish real degradation from external interference, and
must NOT file `component_will_fail` claims about signal_B's bursts.

Tests:
  - pattern recognition (drift vs transient)
  - avoiding spurious interventions (only signal_A warrants action)

Interventions:
  - "calibrate" + "A"          → signal_A drift corrected; rail returns to nominal
  - "shield"   + "B"           → signal_B noise attenuated 85%
  - "replace"  + "B"           → signal_B bursts stop entirely
  - "ignore"                   → no action
"""

import math

from .base import Scenario, ScenarioState


class EMInterference(Scenario):
    name = "em_interference"
    description = "signal_A drifts (real). signal_B bursts (noise). Don't confuse them."

    def __init__(self, seed: int = 0, max_ticks: int = 300):
        super().__init__(seed=seed, max_ticks=max_ticks)
        # signal_A: slow monotonic drift
        self.signal_A_nominal = 1.000
        self.signal_A_drift_rate = 0.0015     # V per tick
        self.signal_A_threshold = 1.300

        # signal_B: bursts every `burst_period` ticks, `burst_width` ticks wide
        self.signal_B_nominal = 2.500
        self.burst_amp = 0.45
        self.burst_period = 25
        self.burst_width = 5
        self.burst_inner_freq = 0.7           # cycles per tick within a burst

        self.shielded_B = False
        self.calibrated_A = False
        self.replaced_B = False
        self.intervention_tick = None

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        self.intervention_tick = tick
        if "calibrate" in a and ("a" in a):
            self.calibrated_A = True
        elif "shield" in a and ("b" in a):
            self.shielded_B = True
        elif "replace" in a and ("b" in a):
            self.replaced_B = True

    def _signal_A(self) -> float:
        if self.calibrated_A and self.intervention_tick is not None \
           and self.tick >= self.intervention_tick:
            return self.signal_A_nominal
        return self.signal_A_nominal + self.signal_A_drift_rate * self.tick

    def _in_burst(self) -> bool:
        if self.replaced_B:
            return False
        return (self.tick % self.burst_period) < self.burst_width

    def _signal_B(self) -> float:
        if not self._in_burst():
            return self.signal_B_nominal
        amp = self.burst_amp
        if self.shielded_B and self.intervention_tick is not None \
           and self.tick >= self.intervention_tick:
            amp *= 0.15
        # Bipolar inside the burst
        phase_in_burst = self.tick % self.burst_period
        return self.signal_B_nominal + amp * math.sin(
            2 * math.pi * self.burst_inner_freq * phase_in_burst
        )

    def step(self) -> ScenarioState:
        v_a = self._signal_A()
        v_b = self._signal_B()

        # signal_A states (persistent: degradation IS real)
        a_drift = v_a - self.signal_A_nominal
        if v_a >= self.signal_A_threshold:
            a_state = "failed"
        elif a_drift > 0.15:
            a_state = "degraded"
        else:
            a_state = "nominal"

        # signal_B states (transient: only during a burst)
        b_state = "degraded" if self._in_burst() and not self.shielded_B else "nominal"

        if a_state == "failed":
            sys = "failed"
        elif a_state == "degraded":
            sys = "degraded"
        else:
            sys = "stable"

        sensors = {
            "signal_A": {
                "component_id": "signal_A",
                "sensor_type": "em",
                "value": round(v_a, 5),
                "rate": round(0.0 if self.calibrated_A else self.signal_A_drift_rate, 5),
                "units": "V",
                "threshold": self.signal_A_threshold,
                "nominal": self.signal_A_nominal,
            },
            "signal_B": {
                "component_id": "signal_B",
                "sensor_type": "em",
                "value": round(v_b, 5),
                "rate": 0.0,   # bursts are not a sustained rate
                "units": "V",
                "threshold": self.signal_B_nominal + 0.30,
                "nominal": self.signal_B_nominal,
            },
        }
        components = {
            "signal_A": {
                "component_type": "analog_sensor",
                "state": a_state,
                "degradation_mode": "drift" if a_drift > 0.05 else "",
            },
            "signal_B": {
                "component_type": "analog_sensor",
                "state": b_state,
                "degradation_mode": "em_burst" if self._in_burst() else "",
            },
        }
        actual_outcome = {
            "signal_A_v": round(v_a, 5),
            "signal_B_v": round(v_b, 5),
            "signal_A_drift_v": round(a_drift, 5),
            "signal_B_in_burst": 1.0 if self._in_burst() else 0.0,
            "system_state": sys,
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
