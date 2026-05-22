"""Shared substrate failure (PCB-level trace crack) kills every sensor on the
substrate simultaneously. Counter-test for "independent component failures".
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


class SharedSubstrateFailure(Scenario):
    name = "shared_substrate"
    description = "All victims fail at identical tick — shared substrate cause."

    dt = 0.05
    default_max_ticks = 240  # 12 s

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "victims": ("S1", "S2", "S3", "S4"),
            "substrate_id": "PCB_A_zone_3",
            "tick_break": 140,
            "V_nominal": 3.3,
            "V_open": 0.0,
            "noise_sigma_v": 0.015,
            **params,
        }
        self._prev = {s: self.params["V_nominal"] for s in self.params["victims"]}

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        broken = self.tick >= p["tick_break"]
        for s in p["victims"]:
            clean = p["V_open"] if broken else p["V_nominal"]
            v = clean + gaussian(rng, p["noise_sigma_v"])
            rate = (clean - self._prev[s]) / self.dt
            self._prev[s] = clean
            add_sensor(st, reading(
                s, "power",
                value=v, rate=rate, units="V",
                threshold=p["V_nominal"] * 0.5, nominal=p["V_nominal"],
            ))
            add_component(st, comp(s, "sensor_io",
                                   state="failed" if broken else "nominal",
                                   degradation_mode="open_circuit" if broken else ""))

        add_measurement(st, "substrate_intact", 0.0 if broken else 1.0)
        if broken:
            set_system_state(st, "failed")
            for s in p["victims"]:
                add_failed(st, s)
            add_event(st, "substrate_trace_crack")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev = {s: self.params["V_nominal"] for s in self.params["victims"]}
