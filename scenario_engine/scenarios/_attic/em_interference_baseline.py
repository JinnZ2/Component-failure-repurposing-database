"""EM interference: a narrowband RF burst couples into an ADC line. Modulates
during the burst window, disappears when the burst ends. No permanent
failure — a naive "open" claim should grade WRONG.
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


class EMInterference(Scenario):
    name = "em_interference"
    description = "Narrowband EM coupling; no permanent failure."

    dt = 0.005
    default_max_ticks = 1600  # 8 s

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "adc": "ADC_in",
            "V_baseline": 1.65,
            "interferer_freq_hz": 217.0,
            "interferer_amp_v": 0.45,
            "tick_burst_start": 400,
            "tick_burst_end": 1000,
            "noise_sigma_v": 0.01,
            **params,
        }
        self._prev = self.params["V_baseline"]

    def _v(self, tick: int) -> float:
        p = self.params
        V = p["V_baseline"]
        if p["tick_burst_start"] <= tick < p["tick_burst_end"]:
            t = tick_to_time(tick, self.dt)
            V += p["interferer_amp_v"] * math.sin(2.0 * math.pi * p["interferer_freq_hz"] * t)
        return V

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        clean = self._v(self.tick)
        v = clean + gaussian(rng, p["noise_sigma_v"])
        rate = (clean - self._prev) / self.dt
        self._prev = clean

        active = p["tick_burst_start"] <= self.tick < p["tick_burst_end"]
        add_sensor(st, reading(
            p["adc"], "em",
            value=v, rate=rate, units="V",
            threshold=p["V_baseline"] + p["interferer_amp_v"],
            nominal=p["V_baseline"],
        ))
        add_component(st, comp(p["adc"], "adc_input",
                               state="degraded" if active else "nominal",
                               degradation_mode="em_coupling" if active else ""))

        add_measurement(st, f"{p['adc']}_v", clean)
        add_measurement(st, "interference_active", 1.0 if active else 0.0)
        if active:
            set_system_state(st, "degraded")
            add_event(st, "em_burst_active")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev = self.params["V_baseline"]
