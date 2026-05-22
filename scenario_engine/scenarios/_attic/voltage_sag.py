"""Brief voltage sag on the main rail — recoverable, no permanent failure.

Tests false-positive rejection: a `component_will_fail` claim is WRONG here.
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


class VoltageSag(Scenario):
    name = "voltage_sag"
    description = "Transient sag; rail recovers. No permanent failure."

    dt = 0.02
    default_max_ticks = 500  # 10 s

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "rail": "V_3V3",
            "V_nominal": 3.3,
            "V_sag": 2.7,
            "tick_sag_start": 150,
            "tick_sag_end": 170,
            "noise_sigma_v": 0.01,
            **params,
        }
        self._prev = self.params["V_nominal"]

    def _v(self, tick: int) -> float:
        p = self.params
        if p["tick_sag_start"] <= tick < p["tick_sag_end"]:
            return p["V_sag"]
        return p["V_nominal"]

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        clean = self._v(self.tick)
        v = clean + gaussian(rng, p["noise_sigma_v"])
        rate = (clean - self._prev) / self.dt
        self._prev = clean

        add_sensor(st, reading(
            p["rail"], "power",
            value=v, rate=rate, units="V",
            threshold=p["V_nominal"] * 0.9, nominal=p["V_nominal"],
        ))
        add_component(st, comp(p["rail"], "rail",
                               state="degraded" if clean < p["V_nominal"] * 0.95 else "nominal",
                               degradation_mode="sag" if clean < p["V_nominal"] * 0.95 else ""))

        add_measurement(st, f"{p['rail']}_v", clean)
        if p["tick_sag_start"] <= self.tick < p["tick_sag_end"]:
            set_system_state(st, "degraded")
            add_event(st, "voltage_sag_active")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev = self.params["V_nominal"]
