"""Sustained brownout: rail droops below the MCU's BOR threshold long enough
that downstream MCU latches into reset. Distinct from `VoltageSag` because the
sag is real and causes a bounded hard-failure window.
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


class Brownout(Scenario):
    name = "brownout"
    description = "MCU resets during brownout; recovers after rail stabilizes."

    dt = 0.05
    default_max_ticks = 300  # 15 s

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "rail": "V_3V3",
            "mcu": "MCU0",
            "V_nominal": 3.3,
            "V_brown": 2.4,
            "V_BOR": 2.7,
            "tick_brown_start": 80,
            "tick_brown_end": 180,
            "reinit_ticks": 20,
            "noise_sigma_v": 0.01,
            **params,
        }
        self._prev = self.params["V_nominal"]

    def _v(self, tick: int) -> float:
        p = self.params
        if p["tick_brown_start"] <= tick < p["tick_brown_end"]:
            return p["V_brown"]
        return p["V_nominal"]

    def _alive(self, tick: int) -> bool:
        p = self.params
        recovery_tick = p["tick_brown_end"] + p["reinit_ticks"]
        return not (p["tick_brown_start"] <= tick < recovery_tick)

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
            threshold=p["V_BOR"], nominal=p["V_nominal"],
        ))
        alive = self._alive(self.tick)
        add_sensor(st, reading(
            p["mcu"], "power",
            value=1.0 if alive else 0.0, rate=0.0, units="bool",
            threshold=0.5, nominal=1.0,
        ))

        rail_state = "degraded" if clean < p["V_BOR"] else "nominal"
        add_component(st, comp(p["rail"], "rail",
                               state=rail_state,
                               degradation_mode="brownout" if rail_state != "nominal" else ""))
        mcu_state = "nominal" if alive else "failed"
        add_component(st, comp(p["mcu"], "mcu",
                               state=mcu_state,
                               degradation_mode="bor_reset" if not alive else ""))

        add_measurement(st, f"{p['rail']}_v", clean)
        add_measurement(st, f"{p['mcu']}_alive", 1.0 if alive else 0.0)

        if not alive:
            set_system_state(st, "failed")
            add_failed(st, p["mcu"])
            add_event(st, "mcu_in_reset")
        elif clean < p["V_BOR"]:
            set_system_state(st, "degraded")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev = self.params["V_nominal"]
