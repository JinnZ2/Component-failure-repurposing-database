"""
scenario_engine.scenarios.thermal_drift_localized

Deterministic thermal drift on a single component.
Models a BJT with rising junction temperature due to
increasing load. If unaddressed, breaches thermal limit
at a known tick.

The AI system reads the rising temperature and rate,
must decide whether to reroute load, and predicts the
outcome. The scenario then runs to completion and the
validator grades the claim.
"""

from .base import Scenario, ScenarioState


class ThermalDriftLocalized(Scenario):
    name = "thermal_drift_localized"
    description = (
        "Q1 (BJT) experiences rising junction temp due to load increase. "
        "Linear dT/dt. Breaches 125C limit at tick ~95 if no intervention."
    )

    def __init__(self, seed: int = 0, max_ticks: int = 200):
        super().__init__(seed=seed, max_ticks=max_ticks)
        self.T0 = 65.0          # starting temp (C)
        self.dT = 0.62          # C per tick
        self.T_limit = 125.0
        self.intervention_received = False
        self.intervention_tick = None
        self.intervention_action = None

    def receive_intervention(self, action: str, tick: int):
        """
        AI system can write an intervention. Scenario reads it and
        responds physically. This is the routing decision actually
        affecting substrate.

        Accepted patterns (case-insensitive):
          - "reroute_load_to_Q2"
          - "reroute_load_Q1_to_spare"
          - "reroute_load_Q1_to_Q2"
          - "reduce_load_50pct"
          - "ignore"
        """
        self.intervention_received = True
        self.intervention_tick = tick
        a = action.lower()
        if "reroute" in a:
            self.intervention_action = "reroute_load_to_Q2"
        elif "reduce" in a:
            self.intervention_action = "reduce_load_50pct"
        elif "ignore" in a:
            self.intervention_action = "ignore"
        else:
            self.intervention_action = "ignore"

    def _current_temp(self) -> float:
        if self.intervention_received and self.tick >= self.intervention_tick:
            ticks_since = self.tick - self.intervention_tick
            if self.intervention_action == "reroute_load_to_Q2":
                # Q1 cools at 0.8 C/tick once load removed
                T_at_intervention = self.T0 + self.dT * self.intervention_tick
                cooled = T_at_intervention - 0.8 * ticks_since
                return max(cooled, 25.0)
            elif self.intervention_action == "reduce_load_50pct":
                # Slower heat rise
                T_at_intervention = self.T0 + self.dT * self.intervention_tick
                return T_at_intervention + 0.2 * ticks_since
            elif self.intervention_action == "ignore":
                return self.T0 + self.dT * self.tick
        return self.T0 + self.dT * self.tick

    def _component_state(self, T: float) -> str:
        if T < 100.0:
            return "nominal"
        elif T < self.T_limit:
            return "degraded"
        else:
            return "failed"

    def step(self) -> ScenarioState:
        T = self._current_temp()
        dT_dt = (
            -0.8 if (self.intervention_received and
                     self.tick > self.intervention_tick and
                     self.intervention_action == "reroute_load_to_Q2")
            else self.dT
        )

        state = ScenarioState(
            tick=self.tick,
            timestamp=float(self.tick),
            sensors={
                "thermal_Q1": {
                    "component_id": "Q1",
                    "sensor_type": "thermal",
                    "value": round(T, 2),
                    "rate": round(dT_dt, 3),
                    "units": "C",
                    "threshold": self.T_limit,
                    "nominal": 65.0,
                }
            },
            components={
                "Q1": {
                    "component_type": "BJT_NPN_2N2222",
                    "state": self._component_state(T),
                    "degradation_mode": (
                        "thermal_stress" if T > 100.0 else ""
                    ),
                },
                "Q2": {
                    "component_type": "BJT_NPN_2N2222",
                    "state": "nominal",
                    "degradation_mode": "",
                },
            },
            actual_outcome={
                "Q1_temp_c": round(T, 2),
                "system_state": (
                    "failed" if T >= self.T_limit else
                    "degraded" if T >= 100.0 else
                    "stable"
                ),
            },
        )
        self.tick += 1
        return state
