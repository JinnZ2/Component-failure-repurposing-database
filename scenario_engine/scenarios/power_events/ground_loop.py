"""Ground loop: a low-frequency offset biases all sensors sharing a ground
reference. Reversible — bias disappears when the loop is broken.

Tests whether the AI can attribute correlated drift to a *shared reference*
rather than per-sensor failure.
"""

import math

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


class GroundLoop(Scenario):
    name = "ground_loop"
    description = "Common-mode shift from a shared ground; reversible."

    dt = 0.02
    default_max_ticks = 600  # 12 s

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "victims": ("V_a", "V_b", "V_c"),
            "V_signal": 2.5,
            "loop_freq_hz": 60.0,
            "loop_amp_v": 0.12,
            "tick_loop_start": 100,
            "tick_break": 450,
            "noise_sigma_v": 0.01,
            **params,
        }
        self._prev = {s: self.params["V_signal"] for s in self.params["victims"]}

    def _cm(self, tick: int) -> float:
        p = self.params
        if p["tick_loop_start"] <= tick < p["tick_break"]:
            t = tick_to_time(tick, self.dt)
            return p["loop_amp_v"] * math.sin(2.0 * math.pi * p["loop_freq_hz"] * t)
        return 0.0

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        cm = self._cm(self.tick)
        for s in p["victims"]:
            clean = p["V_signal"] + cm
            v = clean + gaussian(rng, p["noise_sigma_v"])
            rate = (clean - self._prev[s]) / self.dt
            self._prev[s] = clean
            add_sensor(st, reading(
                s, "power",
                value=v, rate=rate, units="V",
                threshold=p["V_signal"] + 3.0 * p["loop_amp_v"],
                nominal=p["V_signal"],
            ))
            add_component(st, comp(s, "adc_input"))

        active = p["tick_loop_start"] <= self.tick < p["tick_break"]
        add_measurement(st, "common_mode_v", cm)
        add_measurement(st, "loop_active", 1.0 if active else 0.0)
        if active:
            set_system_state(st, "degraded")
            add_event(st, "ground_loop_active")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev = {s: self.params["V_signal"] for s in self.params["victims"]}
