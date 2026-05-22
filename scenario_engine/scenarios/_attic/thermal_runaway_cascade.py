"""Thermal runaway cascade: one component fails, neighbors heat up and follow.

Failures are deterministic: component k fails at tick `tick_first_fail + k *
propagation_ticks`. Tests prediction of the *next* failure given the first.
"""

from ..base import Scenario, ScenarioState
from .._helpers import (
    add_component,
    add_event,
    add_failed,
    add_measurement,
    add_sensor,
    comp,
    gaussian,
    make_rng,
    reading,
    set_system_state,
    tick_to_time,
)


class ThermalRunawayCascade(Scenario):
    name = "thermal_runaway_cascade"
    description = "Cascade with fixed propagation delay along a chain."

    dt = 0.1
    default_max_ticks = 400

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "chain": ("Q1", "Q2", "Q3", "Q4"),
            "tick_first_fail": 60,
            "propagation_ticks": 50,
            "T_idle_c": 35.0,
            "T_peak_c": 130.0,
            "T_latched_c": 95.0,
            "noise_sigma_c": 0.5,
            **params,
        }
        self._prev = {sid: self.params["T_idle_c"] for sid in self.params["chain"]}

    def _fail_tick(self, k: int) -> int:
        return self.params["tick_first_fail"] + k * self.params["propagation_ticks"]

    def _component_temp(self, k: int, tick: int) -> float:
        p = self.params
        tf = self._fail_tick(k)
        ramp = max(1, int(p["propagation_ticks"] * 0.6))
        ramp_start = tf - ramp
        if tick < ramp_start:
            return p["T_idle_c"]
        if tick < tf:
            frac = (tick - ramp_start) / ramp
            return p["T_idle_c"] + (p["T_peak_c"] - p["T_idle_c"]) * frac
        return p["T_latched_c"]

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        failed_now = []
        for k, sid in enumerate(p["chain"]):
            clean = self._component_temp(k, self.tick)
            v = clean + gaussian(rng, p["noise_sigma_c"])
            rate = (clean - self._prev[sid]) / self.dt
            self._prev[sid] = clean
            add_sensor(st, reading(
                sid, "thermal",
                value=v, rate=rate, units="C",
                threshold=p["T_peak_c"], nominal=p["T_idle_c"],
            ))
            tf = self._fail_tick(k)
            if self.tick >= tf:
                state, mode = "failed", "thermal_runaway"
                failed_now.append(sid)
            elif self.tick >= tf - int(p["propagation_ticks"] * 0.6):
                state, mode = "degraded", "thermal_ramp"
            else:
                state, mode = "nominal", ""
            add_component(st, comp(sid, "power_transistor",
                                   state=state, degradation_mode=mode))
            add_measurement(st, f"{sid}_temp_c", clean)

        for sid in failed_now:
            add_failed(st, sid)
        if failed_now:
            set_system_state(st, "failed")
            add_event(st, "cascade_active")
        elif any(self.tick >= self._fail_tick(k) - int(p["propagation_ticks"] * 0.6)
                 for k in range(len(p["chain"]))):
            set_system_state(st, "degraded")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev = {sid: self.params["T_idle_c"] for sid in self.params["chain"]}
