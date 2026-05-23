"""Single impact shock — half-sine pulse on the accelerometer. If the peak
exceeds the crystal's `g_rating`, the crystal latches into a permanent
frequency error.
"""

import math

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


class ImpactShock(Scenario):
    name = "impact_shock"
    description = "Half-sine impact; crystal fails if peak > g_rating."

    dt = 0.002
    default_max_ticks = 2000  # 4 s

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "accel": "ACC1",
            "xtal": "Y1",
            "tick_impact": 1000,         # 2.0 s
            "peak_g": 1500.0,
            "pulse_width_ticks": 750,    # 1.5 ms / 0.002 = 0.75 → keep symmetric across ticks
            "g_rating": 1000.0,
            "noise_sigma_g": 0.3,
            **params,
        }
        # Force odd-symmetric window
        if self.params["pulse_width_ticks"] < 1:
            self.params["pulse_width_ticks"] = 1
        self._prev = 0.0

    def _accel(self, tick: int) -> float:
        p = self.params
        ti = p["tick_impact"]
        pw = p["pulse_width_ticks"]
        if abs(tick - ti) * 2 <= pw:
            phase = math.pi * (tick - (ti - pw / 2)) / pw
            return p["peak_g"] * math.sin(phase)
        return 0.0

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        clean = self._accel(self.tick)
        v = clean + gaussian(rng, p["noise_sigma_g"])
        rate = (clean - self._prev) / self.dt
        self._prev = clean

        add_sensor(st, reading(
            p["accel"], "mechanical",
            value=v, rate=rate, units="g",
            threshold=p["g_rating"], nominal=0.0,
        ))
        add_component(st, comp(p["accel"], "accelerometer"))

        impact_done = self.tick >= p["tick_impact"] + p["pulse_width_ticks"] // 2
        xtal_failed = impact_done and p["peak_g"] > p["g_rating"]
        ppm = 5000.0 if xtal_failed else gaussian(rng, 2.0)
        add_sensor(st, reading(
            p["xtal"], "mechanical",
            value=ppm, rate=0.0, units="ppm",
            threshold=200.0, nominal=0.0,
        ))
        add_component(st, comp(p["xtal"], "crystal_oscillator",
                               state="failed" if xtal_failed else "nominal",
                               degradation_mode="shock_induced_drift" if xtal_failed else ""))

        add_measurement(st, "peak_g", clean)
        add_measurement(st, f"{p['xtal']}_freq_error_ppm", ppm)
        if xtal_failed:
            set_system_state(st, "failed")
            add_failed(st, p["xtal"])
            add_event(st, "xtal_shock_damaged")
        elif abs(clean) > 0.5 * p["g_rating"]:
            set_system_state(st, "degraded")
            add_event(st, "impact_in_progress")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev = 0.0
