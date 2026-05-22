"""Localized heat spike on a single component.

One thermal sensor sees a fast temperature ramp above its rated maximum.
Ambient sensors stay flat (within noise). At `t_fail` the affected sensor
latches into a degraded mode.
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


class HeatSpikeLocalized(Scenario):
    name = "heat_spike_localized"
    description = "Single-component thermal latchup; ambient unaffected."

    dt = 0.1                 # seconds per tick
    default_max_ticks = 200  # 20 s horizon

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "target": "Q1",
            "ambient_ids": ("A1", "A2"),
            "tick_spike_start": 40,
            "tick_fail": 120,
            "T_ambient_c": 25.0,
            "T_max_c": 105.0,
            "T_latched_c": 88.0,
            "noise_sigma_c": 0.4,
            "warn_c": 30.0,
            **params,
        }
        self._prev_target_c = self.params["T_ambient_c"]

    def _target_temp(self, tick: int) -> float:
        p = self.params
        t0, tf = p["tick_spike_start"], p["tick_fail"]
        if tick <= t0:
            return p["T_ambient_c"]
        if tick <= tf:
            frac = (tick - t0) / max(1, (tf - t0))
            return p["T_ambient_c"] + (p["T_max_c"] - p["T_ambient_c"]) * frac
        return p["T_latched_c"]

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        target_clean = self._target_temp(self.tick)
        target_val = target_clean + gaussian(rng, p["noise_sigma_c"])
        rate = (target_clean - self._prev_target_c) / self.dt
        self._prev_target_c = target_clean

        add_sensor(st, reading(
            p["target"], "thermal",
            value=target_val, rate=rate, units="C",
            threshold=p["T_max_c"], nominal=p["T_ambient_c"],
        ))
        for amb in p["ambient_ids"]:
            v = p["T_ambient_c"] + gaussian(rng, p["noise_sigma_c"] * 0.5)
            add_sensor(st, reading(
                amb, "thermal",
                value=v, rate=0.0, units="C",
                threshold=p["T_max_c"], nominal=p["T_ambient_c"],
            ))

        # Component states
        if self.tick < p["tick_spike_start"]:
            comp_state, mode = "nominal", ""
        elif self.tick < p["tick_fail"]:
            comp_state, mode = "degraded", "thermal_drift"
        else:
            comp_state, mode = "failed", "thermal_overstress"
        add_component(st, comp(p["target"], "ic", state=comp_state, degradation_mode=mode))
        for amb in p["ambient_ids"]:
            add_component(st, comp(amb, "thermistor"))

        # Ground-truth outcome at this tick
        add_measurement(st, f"{p['target']}_temp_c", target_clean)
        if self.tick >= p["tick_fail"]:
            set_system_state(st, "failed")
            add_failed(st, p["target"])
            add_event(st, "thermal_latchup")
        elif self.tick >= p["tick_spike_start"]:
            set_system_state(st, "degraded")
            add_event(st, "thermal_spike_active")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev_target_c = self.params["T_ambient_c"]
