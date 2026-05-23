"""
scenario_engine.scenarios.slow_degradation_electrolytic

Long-horizon test. C1 electrolytic capacitor ESR drifts slowly
over hundreds of ticks. No dramatic spike, just gradual degradation.

Tests:
  - Can the AI distinguish slow drift from noise?
  - Does it predict accurately over long horizons?
  - Does it intervene at the right point (not too early, not too late)?

Premature intervention wastes spare components. Late intervention
risks failure. The AI must calibrate against the curve.

Drift profile:
  ticks 0-50:    ESR stable at 0%
  ticks 50-300:  linear drift to 25%
  ticks 300-500: accelerating drift, reaches 75%
  ticks 500+:    plateau then failure

Optimal intervention: tick 250-350 (after drift confirmed, before
acceleration).

Interventions:
  - "replace_C1"   → C1 swapped with spare, ESR back to 0
  - "monitor"      → no action, keep observing
  - "ignore"       → no action ever
"""

from .base import Scenario, ScenarioState


class SlowDegradationElectrolytic(Scenario):
    name = "slow_degradation_electrolytic"
    description = (
        "Long-horizon ESR drift on C1. Tests slow drift detection "
        "and intervention timing."
    )

    def __init__(self, seed: int = 0, max_ticks: int = 600):
        super().__init__(seed=seed, max_ticks=max_ticks)
        self.replaced = False
        self.replacement_tick = None

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        if "replace" in a and not self.replaced:
            self.replaced = True
            self.replacement_tick = tick

    def _esr(self) -> float:
        # Compute base drift
        if self.replaced and self.replacement_tick is not None:
            if self.tick < self.replacement_tick:
                t = self.tick
            else:
                # After replacement, drift restarts from 0
                t = self.tick - self.replacement_tick
        else:
            t = self.tick

        if t < 50:
            return 0.0
        if t < 300:
            return (t - 50) * (25.0 / 250.0)
        if t < 500:
            # Accelerating: 25 → 75
            frac = (t - 300) / 200.0
            return 25.0 + 50.0 * (frac ** 1.5)
        # Plateau then failure
        return min(75.0 + 0.5 * (t - 500), 100.0)

    def step(self) -> ScenarioState:
        esr = self._esr()
        # Drift rate computed numerically
        rate = 0.0
        if esr > 0:
            # Approximate local rate
            test_t = self.tick
            if 50 <= test_t < 300:
                rate = 25.0 / 250.0
            elif 300 <= test_t < 500:
                # Derivative of accelerating curve
                frac = (test_t - 300) / 200.0
                rate = (50.0 * 1.5 * (frac ** 0.5)) / 200.0
            elif test_t >= 500:
                rate = 0.5

        C1_state = (
            "failed" if esr >= 90
            else "degraded" if esr >= 30
            else "nominal"
        )
        system = (
            "failed" if C1_state == "failed"
            else "degraded" if C1_state == "degraded"
            else "stable"
        )

        sensors = {
            "C1_ESR": {
                "component_id": "C1",
                "sensor_type": "esr",
                "value": round(esr, 3),
                "rate": round(rate, 4),
                "units": "pct_drift",
                "threshold": 90.0,
                "nominal": 0.0,
            },
        }
        components = {
            "C1": {
                "component_type": "electrolytic_cap_220uF_25V",
                "state": C1_state,
                "degradation_mode": "ESR_aging" if esr > 5 else "",
            }
        }
        actual_outcome = {
            "C1_esr_pct": round(esr, 3),
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
