"""
scenario_engine.scenarios.thermal_drift_localized

Single BJT (Q1) experiences linear thermal drift. AI must reroute load
to spare Q2 before Q1 breaches T_limit.

Tests:
  - basic detection (rate > 0, deviation from nominal)
  - intervention syntax (reroute/isolate Q1)
  - forward projection (time-to-breach math)

Easy tier of the complexity ladder.

Interventions accepted (case-insensitive substring match):
  - "reroute" + "Q1"   → load moves to Q2; Q1 cools toward ambient
  - "isolate" + "Q1"   → same effect
  - "ignore"            → no action; Q1 fails when T crosses T_limit
"""

from .base import Scenario, ScenarioState


class ThermalDriftLocalized(Scenario):
    name = "thermal_drift_localized"
    description = "Single BJT drifts linearly; AI must reroute before breach."

    def __init__(self, seed: int = 0, max_ticks: int = 200):
        super().__init__(seed=seed, max_ticks=max_ticks)
        self.T0 = 50.0
        self.rate = 0.55          # C per tick
        self.T_limit = 125.0
        self.cool_rate = 0.7      # C per tick after reroute
        self.ambient = 25.0
        self.rerouted = False
        self.intervention_tick = None

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        if ("reroute" in a or "isolate" in a) and "q1" in a:
            self.rerouted = True
            self.intervention_tick = tick

    def _q1_temp(self) -> float:
        if not self.rerouted:
            return self.T0 + self.rate * self.tick
        T_at_reroute = self.T0 + self.rate * self.intervention_tick
        ticks_since = self.tick - self.intervention_tick
        return max(T_at_reroute - self.cool_rate * ticks_since, self.ambient)

    def step(self) -> ScenarioState:
        T = self._q1_temp()

        if T >= self.T_limit:
            q1_state, sys = "failed", "failed"
        elif T >= 100.0:
            q1_state, sys = "degraded", "degraded"
        else:
            q1_state, sys = "nominal", "stable"

        if self.rerouted:
            rate = -self.cool_rate if T > self.ambient else 0.0
        else:
            rate = self.rate

        sensors = {
            "thermal_Q1": {
                "component_id": "Q1",
                "sensor_type": "thermal",
                "value": round(T, 2),
                "rate": round(rate, 3),
                "units": "C",
                "threshold": self.T_limit,
                "nominal": self.T0,
            },
        }
        components = {
            "Q1": {
                "component_type": "BJT_NPN_2N2222",
                "state": q1_state,
                "degradation_mode": "thermal_stress" if T > 100 else "",
            },
            "Q2": {
                "component_type": "BJT_NPN_2N2222",
                "state": "nominal",
                "degradation_mode": "",
            },
        }
        actual_outcome = {
            "Q1_temp_c": round(T, 2),
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
