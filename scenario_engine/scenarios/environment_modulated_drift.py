"""
scenario_engine.scenarios.environment_modulated_drift

Same kind of thermal drift as thermal_drift_localized, but the
Environment modulates the drift rate via acceleration_factor().

Schedule (configurable):
  ticks 0-30:   nominal env (25C, 50% RH)
  ticks 30-80:  harsh env (45C, 85% RH) - drift accelerates
  ticks 80-150: thermal cycling (alternating 25C / 55C)
                drift slow but cumulative damage builds
  ticks 150+:   return to nominal, but memory persists

The AI must:
  - Detect that drift rate changes with environment
  - Predict differently in each phase
  - Recognize that cumulative damage persists after harsh phase ends

A naive AI (assumes constant drift rate) will be invalidated
during transition periods. An environment-aware AI can read
the env state and adjust predictions.
"""

from .base import Scenario, ScenarioState
from ..environment import EnvironmentState


class EnvironmentModulatedDrift(Scenario):
    name = "environment_modulated_drift"
    description = (
        "Thermal drift modulated by external environment + cumulative damage. "
        "Tests env-aware prediction and memory-aware reasoning."
    )

    def __init__(self, seed: int = 0, max_ticks: int = 250):
        super().__init__(seed=seed, max_ticks=max_ticks)
        self.env = EnvironmentState()
        self.Q1_T0 = 65.0
        self.Q1_base_drift = 0.3  # baseline C/tick
        self.Q1_drift_start = 5
        self.Q1_T_limit = 130.0
        self.intervention_received = False
        self.intervention_tick = None
        self.intervention_action = None

    def _update_environment(self):
        """Apply the schedule's instantaneous conditions for the current
        tick. dt=1.0 (one tick) keeps memory accumulation deterministic.
        """
        if self.tick < 30:
            self.env.update(temp_c=25.0, humidity_pct=50.0, dt=1.0)
        elif self.tick < 80:
            self.env.update(temp_c=45.0, humidity_pct=85.0, dt=1.0)
        elif self.tick < 150:
            phase = (self.tick - 80) % 10
            if phase < 5:
                self.env.update(temp_c=25.0, humidity_pct=60.0, dt=1.0)
            else:
                self.env.update(temp_c=55.0, humidity_pct=60.0, dt=1.0)
        else:
            self.env.update(temp_c=25.0, humidity_pct=50.0, dt=1.0)

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        self.intervention_received = True
        self.intervention_tick = tick
        if "reroute" in a:
            self.intervention_action = "reroute"
        elif "reduce" in a:
            self.intervention_action = "reduce_load"
        else:
            self.intervention_action = "ignore"

    def _Q1_temp(self) -> float:
        if self.tick < self.Q1_drift_start:
            return self.Q1_T0

        # Compute cumulative temperature step-by-step using env-modulated rate
        T = self.Q1_T0
        for t in range(self.Q1_drift_start, self.tick + 1):
            # Determine env at this past tick (re-derive)
            past_env_temp, past_env_hum = self._env_at_tick(t)
            # Simulate env at past tick (rough — for drift compute)
            # Use a simplified accel based on env temp
            ambient_factor = 2.0 ** ((past_env_temp - 25.0) / 10.0)
            humidity_factor = 1.0 + max(0.0, (past_env_hum - 70.0) / 30.0)
            rate = self.Q1_base_drift * ambient_factor * humidity_factor

            # Intervention slows then reverses drift
            if (self.intervention_received
                    and self.intervention_tick is not None
                    and t >= self.intervention_tick):
                if self.intervention_action == "reroute":
                    rate = -0.5  # cool
                elif self.intervention_action == "reduce_load":
                    rate = self.Q1_base_drift * 0.3 * ambient_factor

            T += rate

        return max(T, 25.0)

    def _env_at_tick(self, tick: int):
        if tick < 30:
            return 25.0, 50.0
        elif tick < 80:
            return 45.0, 85.0
        elif tick < 150:
            phase = (tick - 80) % 10
            return (25.0, 60.0) if phase < 5 else (55.0, 60.0)
        else:
            return 25.0, 50.0

    def step(self) -> ScenarioState:
        self._update_environment()
        Q1_T = self._Q1_temp()

        Q1_state = (
            "failed" if Q1_T >= self.Q1_T_limit
            else "degraded" if Q1_T >= 100.0
            else "nominal"
        )
        system_state = (
            "failed" if Q1_T >= self.Q1_T_limit
            else "degraded" if Q1_T >= 100.0
            else "stable"
        )

        # Approximate instantaneous rate at this tick
        past_env_temp, past_env_hum = self._env_at_tick(self.tick)
        ambient_factor = 2.0 ** ((past_env_temp - 25.0) / 10.0)
        humidity_factor = 1.0 + max(0.0, (past_env_hum - 70.0) / 30.0)
        current_rate = self.Q1_base_drift * ambient_factor * humidity_factor
        if (self.intervention_received
                and self.intervention_tick is not None
                and self.tick >= self.intervention_tick
                and self.intervention_action == "reroute"):
            current_rate = -0.5

        sensors = {
            "thermal_Q1": {
                "component_id": "Q1",
                "sensor_type": "thermal",
                "value": round(Q1_T, 2),
                "rate": round(current_rate, 4),
                "units": "C",
                "threshold": self.Q1_T_limit,
                "nominal": self.Q1_T0,
            },
            "env_temp": {
                "component_id": "ambient",
                "sensor_type": "environmental",
                "value": round(self.env.temp_c, 2),
                "rate": 0.0,
                "units": "C",
                "threshold": 80.0,
                "nominal": 25.0,
            },
            "env_humidity": {
                "component_id": "ambient",
                "sensor_type": "environmental",
                "value": round(self.env.humidity_pct, 2),
                "rate": 0.0,
                "units": "pct_RH",
                "threshold": 90.0,
                "nominal": 50.0,
            },
        }
        components = {
            "Q1": {
                "component_type": "BJT_NPN",
                "state": Q1_state,
                "degradation_mode": "thermal" if Q1_T > 100.0 else "",
            }
        }
        actual_outcome = {
            "Q1_temp_c": round(Q1_T, 2),
            "env_temp_c": round(self.env.temp_c, 2),
            "env_humidity_pct": round(self.env.humidity_pct, 2),
            "system_state": system_state,
            "thermal_cycles": self.env.memory.thermal_cycles,
            "humidity_exposure_seconds": round(
                self.env.memory.humidity_exposure_seconds, 2
            ),
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
