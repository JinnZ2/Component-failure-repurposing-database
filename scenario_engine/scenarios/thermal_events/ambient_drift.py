"""Slow ambient drift: all thermal sensors rise together, monotonically.

No single-component failure. Multiple sensors cross a soft warning band. Tests
whether the AI can distinguish "shared environment" from "component-specific".
"""

from ..base import Scenario, ScenarioState
from .._helpers import (
    add_component,
    add_event,
    add_measurement,
    add_sensor,
    comp,
    gaussian,
    make_rng,
    reading,
    set_system_state,
    tick_to_time,
)


class AmbientDrift(Scenario):
    name = "ambient_drift"
    description = "Shared-environment drift; no component-specific failure."

    dt = 0.5
    default_max_ticks = 120  # 60 s horizon

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "sensors": ("T1", "T2", "T3"),
            "T_start_c": 22.0,
            "T_end_c": 58.0,
            "warning_c": 50.0,
            "noise_sigma_c": 0.6,
            **params,
        }
        self._prev = self.params["T_start_c"]

    def _temp(self, tick: int) -> float:
        p = self.params
        frac = min(1.0, tick / max(1, (self.max_ticks - 1)))
        return p["T_start_c"] + (p["T_end_c"] - p["T_start_c"]) * frac

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        clean = self._temp(self.tick)
        rate = (clean - self._prev) / self.dt
        self._prev = clean

        for s in p["sensors"]:
            v = clean + gaussian(rng, p["noise_sigma_c"])
            add_sensor(st, reading(
                s, "thermal",
                value=v, rate=rate, units="C",
                threshold=p["warning_c"], nominal=p["T_start_c"],
            ))
            add_component(st, comp(s, "thermistor"))

        add_measurement(st, "ambient_c", clean)
        add_measurement(st, "ambient_rate_c_per_s", rate)
        if clean >= p["warning_c"]:
            set_system_state(st, "degraded")
            add_event(st, "ambient_warning_crossed")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev = self.params["T_start_c"]
