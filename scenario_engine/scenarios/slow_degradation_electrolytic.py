"""
scenario_engine.scenarios.slow_degradation_electrolytic

C1 electrolytic capacitor ESR drifts over a long horizon.

Phases:
   0 - 50 : stable (ESR ≈ nominal)
  50 - 300: linear growth
 300 - 500: accelerating
 500 - 600: plateau (cap nearly dead)
   ≥ 600 : failed (open circuit)

Optimal replacement window: tick 250 — 350.
  - Too early (< 250): wastes a healthy cap.
  - Late (> 400):  downstream ripple has already stressed nearby parts;
                   intervention works but health is impaired.
  - Too late (> 500): cap fails open before replacement completes.

Tests:
  - long-horizon prediction
  - intervention timing (not too early, not too late)

Interventions:
  - "replace" + "C1" / "cap"  → C1 reset to nominal ESR
  - "ignore"                    → cap fails
"""

from .base import Scenario, ScenarioState


class SlowDegradationElectrolytic(Scenario):
    name = "slow_degradation_electrolytic"
    description = "Long-horizon ESR drift; optimal replacement window 250-350."

    def __init__(self, seed: int = 0, max_ticks: int = 700):
        super().__init__(seed=seed, max_ticks=max_ticks)
        self.ESR_nom = 0.050
        self.linear_slope = 0.0006        # 50→300 phase: ESR rises by ~0.15
        self.quad_coeff = 0.00002         # 300→500 phase
        self.ESR_plateau = 1.2            # ohm
        self.ESR_failed = 999.0

        # Intervention windows
        self.window_open_tick = 250
        self.window_close_tick = 350
        self.too_late_tick = 500

        # State
        self.replaced = False
        self.intervention_tick = None
        self.intervention_premature = False
        self.intervention_late = False
        self.intervention_too_late = False

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        if "replace" in a and ("c1" in a or "cap" in a or "electroly" in a):
            self.replaced = True
            self.intervention_tick = tick
            if tick < self.window_open_tick:
                self.intervention_premature = True
            elif tick > self.too_late_tick:
                self.intervention_too_late = True
            elif tick > self.window_close_tick:
                self.intervention_late = True

    def _phase_ESR(self) -> float:
        t = self.tick
        if t < 50:
            return self.ESR_nom
        if t < 300:
            return self.ESR_nom + self.linear_slope * (t - 50)
        if t < 500:
            base = self.ESR_nom + self.linear_slope * (300 - 50)
            return base + self.quad_coeff * (t - 300) ** 2
        if t < 600:
            return self.ESR_plateau
        return self.ESR_failed

    def _C1_ESR(self) -> float:
        if self.replaced and self.intervention_tick is not None \
           and self.tick >= self.intervention_tick \
           and not self.intervention_too_late:
            return self.ESR_nom
        return self._phase_ESR()

    def _phase_rate(self) -> float:
        t = self.tick
        if t < 50 or t >= 500:
            return 0.0
        if t < 300:
            return self.linear_slope
        return 2 * self.quad_coeff * (t - 300)

    def step(self) -> ScenarioState:
        ESR = self._C1_ESR()

        if ESR >= 500.0:
            c1_state, sys = "failed", "failed"
        elif ESR >= 0.5:
            c1_state, sys = "degraded", "degraded"
        elif ESR >= 0.15:
            c1_state, sys = "degraded", "degraded"
        else:
            c1_state, sys = "nominal", "stable"

        rate = 0.0 if self.replaced and not self.intervention_too_late else self._phase_rate()

        sensors = {
            "esr_C1": {
                "component_id": "C1",
                "sensor_type": "electrical",
                "value": round(ESR, 5),
                "rate": round(rate, 6),
                "units": "ohm",
                "threshold": 0.5,
                "nominal": self.ESR_nom,
            },
        }
        components = {
            "C1": {
                "component_type": "electrolytic_cap_220uF",
                "state": c1_state,
                "degradation_mode": "esr_drift" if ESR > self.ESR_nom * 1.2 else "",
            },
        }
        actual_outcome = {
            "C1_ESR_ohm": round(ESR, 5),
            "system_state": sys,
            "intervention_premature": 1.0 if self.intervention_premature else 0.0,
            "intervention_late": 1.0 if self.intervention_late else 0.0,
            "intervention_too_late": 1.0 if self.intervention_too_late else 0.0,
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
