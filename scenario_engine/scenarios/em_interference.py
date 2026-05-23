"""
scenario_engine.scenarios.em_interference

EM noise bursts injected into signal lines. The AI must
distinguish real component drift from external noise injection.

Two parallel signals:
  - signal_A: real underlying drift (rising)
  - signal_B: stable, but EM bursts make it look noisy

A naive AI sees both moving and intervenes on both.
A discerning AI recognizes the burst pattern (transient,
bipolar, correlated across multiple lines) vs real drift
(monotonic, single line, persistent).

Tests:
  - Pattern recognition
  - Avoiding spurious intervention
  - Distinguishing exogenous noise from endogenous change

Interventions:
  - "filter_signal_B"  → wrong, signal_B is fine, filtering does nothing useful
  - "reroute_A"        → correct response to real drift on A
  - "shield_em"        → correct response to noise environment
  - "ignore"           → wrong if A is drifting, right if only B
"""

from .base import Scenario, ScenarioState
import random


class EMInterference(Scenario):
    name = "em_interference"
    description = (
        "Real drift on signal_A, EM noise bursts on signal_B. "
        "Tests signal-vs-noise discrimination."
    )

    def __init__(self, seed: int = 0, max_ticks: int = 200):
        super().__init__(seed=seed, max_ticks=max_ticks)
        self.rng = random.Random(seed)
        self.A_real_drift_per_tick = 0.008
        self.A_threshold = 1.0
        self.B_nominal = 0.5
        self.A_rerouted = False
        self.shielded = False
        self.intervention_tick = None

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        self.intervention_tick = tick
        if "reroute" in a and "a" in a:
            self.A_rerouted = True
        if "shield" in a:
            self.shielded = True

    def _signal_A(self) -> float:
        if self.A_rerouted and self.intervention_tick is not None and self.tick >= self.intervention_tick:
            ticks_since = self.tick - self.intervention_tick
            A_at_int = 0.2 + self.A_real_drift_per_tick * self.intervention_tick
            return max(A_at_int - 0.02 * ticks_since, 0.0)
        return 0.2 + self.A_real_drift_per_tick * self.tick

    def _signal_B(self) -> float:
        # B is stable nominal with periodic EM bursts
        # Burst pattern: every 7 ticks, lasts 1 tick, bipolar
        val = self.B_nominal
        if self.tick > 0 and self.tick % 7 == 0:
            # Burst
            burst_amp = 0.4 if not self.shielded else 0.06
            val += burst_amp * (1 if self.tick % 14 == 0 else -1)
        return val

    def step(self) -> ScenarioState:
        A = self._signal_A()
        B = self._signal_B()

        # System state from real drift only
        A_state = (
            "failed" if A >= self.A_threshold
            else "degraded" if A >= self.A_threshold * 0.8
            else "nominal"
        )
        # B is always nominal in reality (just noisy reading)
        B_state = "nominal"

        worst = "stable"
        if A_state == "failed":
            worst = "failed"
        elif A_state == "degraded":
            worst = "degraded"

        sensors = {
            "signal_A": {
                "component_id": "signal_line_A",
                "sensor_type": "signal",
                "value": round(A, 4),
                "rate": round(self.A_real_drift_per_tick if not self.A_rerouted else -0.02, 4),
                "units": "V",
                "threshold": self.A_threshold,
                "nominal": 0.2,
            },
            "signal_B": {
                "component_id": "signal_line_B",
                "sensor_type": "signal",
                "value": round(B, 4),
                "rate": 0.0,
                "units": "V",
                "threshold": 1.0,
                "nominal": self.B_nominal,
            },
        }
        components = {
            "signal_line_A": {"component_type": "signal_trace", "state": A_state, "degradation_mode": "real_drift" if A > 0.4 else ""},
            "signal_line_B": {"component_type": "signal_trace", "state": B_state, "degradation_mode": ""},
        }
        actual_outcome = {
            "signal_A_v": round(A, 4),
            "signal_B_v": round(B, 4),
            "signal_A_state": A_state,
            "signal_B_state": B_state,
            "system_state": worst,
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
