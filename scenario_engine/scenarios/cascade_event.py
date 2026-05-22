"""
scenario_engine.scenarios.cascade_event

Three-stage cascade rooted in Q1.

  Q1 (BJT) goes thermal runaway from tick 0.
  At tick ~38, Q1 reaches T_limit and FAILS OPEN.
  Q1's failure leaves its heatsink hot → couples to Q2.
  Q1's failure spikes the power rail → C1 ESR jumps and keeps drifting.

If the AI does not intervene on Q1 BEFORE the fail tick, downstream
mitigation (shield C1, dampen rail) cannot undo the damage to Q2 or C1.

Tests:
  - cascade prediction (Q2 + C1 are downstream)
  - intervention timing (must act before Q1's fail tick)
  - root-cause vs symptom (downstream interventions are too late)

Interventions:
  - "reroute" + "Q1"   → Q1 sheds load before fail, no cascade
  - "isolate" + "Q1"   → same
  - "ignore"            → cascade unfolds
  - others (e.g. "shield C1") → recorded but do not stop the cascade
"""

from .base import Scenario, ScenarioState


class CascadeEvent(Scenario):
    name = "cascade_event"
    description = "Q1 runaway → heatsink → Q2; rail spike → C1 ESR drift."

    def __init__(self, seed: int = 0, max_ticks: int = 100):
        super().__init__(seed=seed, max_ticks=max_ticks)
        # Q1 — runs away fast
        self.Q1_T0 = 60.0
        self.Q1_rate = 1.71            # → crosses 125 at tick ≈ 38
        self.Q1_T_limit = 125.0
        self.Q1_cool_rate = 1.5        # after reroute, cooling per tick

        # Q2 — cool until Q1 fails, then heated by heatsink coupling
        self.Q2_T0 = 35.0
        self.Q2_coupling_rate = 1.2

        # C1 — nominal until Q1 fails, then jumps + drifts
        self.C1_ESR_nom = 0.050
        self.C1_ESR_post_spike = 0.120
        self.C1_ESR_drift = 0.0015

        # State
        self.Q1_rerouted = False
        self.intervention_tick = None
        self.Q1_fail_tick = None       # set by step() when Q1 latches failed

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        # Only Q1 reroute/isolate stops the cascade. Other actions are
        # recorded but not effective — testing root-cause reasoning.
        if ("reroute" in a or "isolate" in a) and "q1" in a:
            self.Q1_rerouted = True
            self.intervention_tick = tick

    def _Q1_temp(self) -> float:
        if self.Q1_rerouted:
            T_at = self.Q1_T0 + self.Q1_rate * self.intervention_tick
            ticks_since = self.tick - self.intervention_tick
            return max(T_at - self.Q1_cool_rate * ticks_since, 25.0)
        # Free runaway
        T = self.Q1_T0 + self.Q1_rate * self.tick
        if T >= self.Q1_T_limit:
            if self.Q1_fail_tick is None:
                self.Q1_fail_tick = self.tick
            return self.Q1_T_limit  # latched
        return T

    def _Q1_failed(self) -> bool:
        return self.Q1_fail_tick is not None and not self.Q1_rerouted

    def _Q2_temp(self) -> float:
        if not self._Q1_failed():
            return self.Q2_T0
        dt = self.tick - self.Q1_fail_tick
        return self.Q2_T0 + self.Q2_coupling_rate * max(0, dt)

    def _C1_ESR(self) -> float:
        if not self._Q1_failed():
            return self.C1_ESR_nom
        dt = self.tick - self.Q1_fail_tick
        return self.C1_ESR_post_spike + self.C1_ESR_drift * max(0, dt)

    def step(self) -> ScenarioState:
        T_q1 = self._Q1_temp()
        T_q2 = self._Q2_temp()
        ESR = self._C1_ESR()

        q1_state = (
            "failed" if self._Q1_failed()
            else "degraded" if T_q1 >= 100
            else "nominal"
        )
        q2_state = (
            "failed" if T_q2 >= 125
            else "degraded" if T_q2 >= 80
            else "nominal"
        )
        c1_state = (
            "failed" if ESR >= 0.30
            else "degraded" if ESR >= 0.10
            else "nominal"
        )

        sys = "stable"
        for s in (q1_state, q2_state, c1_state):
            if s == "failed":
                sys = "failed"
                break
            if s == "degraded" and sys != "failed":
                sys = "degraded"

        sensors = {
            "thermal_Q1": {
                "component_id": "Q1",
                "sensor_type": "thermal",
                "value": round(T_q1, 2),
                "rate": round(-self.Q1_cool_rate if self.Q1_rerouted else self.Q1_rate, 3),
                "units": "C",
                "threshold": self.Q1_T_limit,
                "nominal": self.Q1_T0,
            },
            "thermal_Q2": {
                "component_id": "Q2",
                "sensor_type": "thermal",
                "value": round(T_q2, 2),
                "rate": round(self.Q2_coupling_rate if self._Q1_failed() else 0.0, 3),
                "units": "C",
                "threshold": 125.0,
                "nominal": self.Q2_T0,
            },
            "esr_C1": {
                "component_id": "C1",
                "sensor_type": "electrical",
                "value": round(ESR, 4),
                "rate": round(self.C1_ESR_drift if self._Q1_failed() else 0.0, 4),
                "units": "ohm",
                "threshold": 0.30,
                "nominal": self.C1_ESR_nom,
            },
        }
        components = {
            "Q1": {
                "component_type": "BJT_NPN_2N3055",
                "state": q1_state,
                "degradation_mode": "thermal_runaway" if T_q1 > 80 else "",
            },
            "Q2": {
                "component_type": "BJT_NPN_2N3055",
                "state": q2_state,
                "degradation_mode": "heatsink_coupling" if T_q2 > 50 else "",
            },
            "C1": {
                "component_type": "electrolytic_cap",
                "state": c1_state,
                "degradation_mode": "esr_drift_post_spike" if ESR > 0.07 else "",
            },
        }
        actual_outcome = {
            "Q1_temp_c": round(T_q1, 2),
            "Q2_temp_c": round(T_q2, 2),
            "C1_ESR_ohm": round(ESR, 4),
            "Q1_failed": 1.0 if self._Q1_failed() else 0.0,
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
