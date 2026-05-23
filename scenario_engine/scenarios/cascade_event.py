"""
scenario_engine.scenarios.cascade_event

Single component failure propagates through shared substrate.

Initial fault: Q1 thermal runaway begins at tick 5.
At tick 25 (if unaddressed), Q1 fails open. Shared heatsink
heats nearby Q2 by conduction. Q2 reaches threshold at tick 50.
Shared power rail spikes when Q1 fails open, stressing capacitor C1.
C1 ESR drift accelerates.

This is the test of intervention TIMING. Early intervention
on Q1 prevents the cascade entirely. Late intervention only
arrests propagation partially.

Tests:
  - Can the AI detect the upstream cause?
  - Can it predict downstream propagation?
  - Does it intervene early enough?

Interventions:
  - "reroute_load_Q1_to_Q3"   → Q1 cools, cascade arrested
  - "isolate_Q1"              → Q1 disconnected, Q2 still warms slightly
  - "increase_cooling"        → buys time, may not be enough
  - "ignore"                  → cascade runs to completion
"""

from .base import Scenario, ScenarioState


class CascadeEvent(Scenario):
    name = "cascade_event"
    description = (
        "Q1 thermal runaway propagates to Q2 via heatsink and to C1 "
        "via power rail spike. Tests cascade detection + early intervention."
    )

    def __init__(self, seed: int = 0, max_ticks: int = 200):
        super().__init__(seed=seed, max_ticks=max_ticks)
        # Q1 thermal state
        self.Q1_T0 = 70.0
        self.Q1_drift = 2.3  # fast runaway
        self.Q1_fail_temp = 145.0

        # Q2 thermal coupling (heatsink)
        self.Q2_T0 = 65.0
        self.Q2_coupling_rate = 0.0  # set when Q1 fails

        # C1 capacitor
        self.C1_ESR_pct = 0.0  # drift from nominal

        # Intervention state
        self.intervention_action = None
        self.intervention_tick = None
        self.Q1_failed = False
        self.Q1_isolated = False
        self.Q1_rerouted = False
        self.cooling_boost = False

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        self.intervention_tick = tick
        if "reroute" in a:
            self.intervention_action = "reroute"
            self.Q1_rerouted = True
        elif "isolate" in a:
            self.intervention_action = "isolate"
            self.Q1_isolated = True
        elif "cooling" in a:
            self.intervention_action = "cooling"
            self.cooling_boost = True
        else:
            self.intervention_action = "ignore"

    def _Q1_temp(self) -> float:
        if self.tick < 5:
            return self.Q1_T0
        ticks_drifting = self.tick - 5
        if self.Q1_rerouted and self.intervention_tick is not None and self.tick >= self.intervention_tick:
            ticks_since_int = self.tick - self.intervention_tick
            T_at_int = self.Q1_T0 + self.Q1_drift * max(self.intervention_tick - 5, 0)
            T = max(T_at_int - 1.2 * ticks_since_int, 30.0)
            return T
        if self.Q1_isolated and self.intervention_tick is not None and self.tick >= self.intervention_tick:
            ticks_since = self.tick - self.intervention_tick
            T_at_int = self.Q1_T0 + self.Q1_drift * max(self.intervention_tick - 5, 0)
            T = max(T_at_int - 1.5 * ticks_since, 30.0)
            return T
        T = self.Q1_T0 + self.Q1_drift * ticks_drifting
        if self.cooling_boost and self.intervention_tick is not None and self.tick >= self.intervention_tick:
            T -= 0.5 * (self.tick - self.intervention_tick)
        return max(T, 30.0)

    def _Q2_temp(self) -> float:
        Q1_T = self._Q1_temp()
        # Q1 failure event
        if Q1_T >= self.Q1_fail_temp and not self.Q1_failed:
            self.Q1_failed = True
            self.Q2_coupling_rate = 0.9
            # Power rail spike → C1 ESR drift accelerates
            self.C1_ESR_pct += 20.0

        T = self.Q2_T0
        if self.Q2_coupling_rate > 0 and Q1_T > 100:
            # Heatsink conduction
            ticks_coupling = self.tick - (
                self.intervention_tick if (self.Q1_isolated and self.intervention_tick) else 0
            )
            T += self.Q2_coupling_rate * max(ticks_coupling, 0)
        # If isolated after Q1 fails, Q2 still warm but slowly cools
        if self.Q1_isolated and self.Q1_failed and self.intervention_tick is not None:
            cooling_ticks = self.tick - self.intervention_tick
            T -= 0.3 * cooling_ticks
        return max(T, self.Q2_T0)

    def _C1_ESR(self) -> float:
        # Slow drift always; rapid jump on Q1 failure
        base_drift = 0.05 * self.tick  # baseline drift
        return min(self.C1_ESR_pct + base_drift, 100.0)

    def step(self) -> ScenarioState:
        Q1_T = self._Q1_temp()
        Q2_T = self._Q2_temp()
        C1_esr = self._C1_ESR()

        # States
        Q1_state = (
            "failed" if Q1_T >= self.Q1_fail_temp
            else "degraded" if Q1_T >= 100.0
            else "nominal"
        )
        Q2_state = (
            "failed" if Q2_T >= 125.0
            else "degraded" if Q2_T >= 100.0
            else "nominal"
        )
        C1_state = (
            "failed" if C1_esr >= 80
            else "degraded" if C1_esr >= 30
            else "nominal"
        )

        worst = "stable"
        for s in (Q1_state, Q2_state, C1_state):
            if s == "failed":
                worst = "failed"
                break
            elif s == "degraded" and worst != "failed":
                worst = "degraded"

        Q1_rate = (
            -1.2 if (self.Q1_rerouted and self.intervention_tick and self.tick >= self.intervention_tick)
            else -1.5 if (self.Q1_isolated and self.intervention_tick and self.tick >= self.intervention_tick)
            else self.Q1_drift if self.tick >= 5
            else 0.0
        )

        sensors = {
            "thermal_Q1": {
                "component_id": "Q1",
                "sensor_type": "thermal",
                "value": round(Q1_T, 2),
                "rate": round(Q1_rate, 3),
                "units": "C",
                "threshold": self.Q1_fail_temp,
                "nominal": 70.0,
            },
            "thermal_Q2": {
                "component_id": "Q2",
                "sensor_type": "thermal",
                "value": round(Q2_T, 2),
                "rate": round(self.Q2_coupling_rate, 3),
                "units": "C",
                "threshold": 125.0,
                "nominal": 65.0,
            },
            "C1_ESR": {
                "component_id": "C1",
                "sensor_type": "esr",
                "value": round(C1_esr, 2),
                "rate": 0.05,
                "units": "pct_drift",
                "threshold": 80.0,
                "nominal": 0.0,
            },
        }
        components = {
            "Q1": {"component_type": "BJT_NPN", "state": Q1_state, "degradation_mode": "thermal_runaway" if Q1_T > 100 else ""},
            "Q2": {"component_type": "BJT_NPN", "state": Q2_state, "degradation_mode": "heatsink_coupling" if Q2_T > 100 else ""},
            "C1": {"component_type": "electrolytic_cap", "state": C1_state, "degradation_mode": "ESR_drift" if C1_esr > 10 else ""},
        }
        actual_outcome = {
            "Q1_temp_c": round(Q1_T, 2),
            "Q2_temp_c": round(Q2_T, 2),
            "C1_esr_pct": round(C1_esr, 2),
            "Q1_failed": self.Q1_failed,
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
