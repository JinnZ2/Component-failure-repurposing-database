"""Radiation burst: SEU (transient bit flip) at one tick; SEL (latchup
requiring power cycle) over a bounded window. Tests transient-vs-latching
discrimination.
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


class RadiationBurst(Scenario):
    name = "radiation_burst"
    description = "SEU transient + SEL latched window with power-cycle recovery."

    dt = 0.02
    default_max_ticks = 600  # 12 s

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "dosimeter": "RAD1",
            "memory": "MEM0",
            "regulator": "LDO1",
            "bg_rad_uSv_h": 0.1,
            "tick_seu": 150,
            "seu_rad_uSv_h": 50.0,
            "tick_sel_start": 300,
            "tick_sel_clear": 475,
            "sel_rad_uSv_h": 800.0,
            "noise_sigma_uSv_h": 0.02,
            **params,
        }
        self._prev = self.params["bg_rad_uSv_h"]

    def _rad(self, tick: int) -> float:
        p = self.params
        if tick == p["tick_seu"]:
            return p["seu_rad_uSv_h"]
        if p["tick_sel_start"] <= tick < p["tick_sel_clear"]:
            return p["sel_rad_uSv_h"]
        return p["bg_rad_uSv_h"]

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        clean = self._rad(self.tick)
        v = clean + gaussian(rng, p["noise_sigma_uSv_h"])
        rate = (clean - self._prev) / self.dt
        self._prev = clean

        add_sensor(st, reading(
            p["dosimeter"], "em",
            value=v, rate=rate, units="uSv/h",
            threshold=10.0, nominal=p["bg_rad_uSv_h"],
        ))
        add_component(st, comp(p["dosimeter"], "dosimeter"))

        parity_ok = self.tick != p["tick_seu"]
        add_sensor(st, reading(
            p["memory"], "em",
            value=1.0 if parity_ok else 0.0, rate=0.0, units="bool",
            threshold=0.5, nominal=1.0,
        ))
        add_component(st, comp(p["memory"], "sram",
                               state="degraded" if not parity_ok else "nominal",
                               degradation_mode="SEU_bit_flip" if not parity_ok else ""))

        sel_active = p["tick_sel_start"] <= self.tick < p["tick_sel_clear"]
        i = 0.9 if sel_active else 0.05
        add_sensor(st, reading(
            p["regulator"], "power",
            value=i, rate=0.0, units="A",
            threshold=0.5, nominal=0.05,
        ))
        add_component(st, comp(p["regulator"], "ldo",
                               state="failed" if sel_active else "nominal",
                               degradation_mode="SEL_latched" if sel_active else ""))

        add_measurement(st, "rad_uSv_h", clean)
        add_measurement(st, f"{p['memory']}_parity_ok", 1.0 if parity_ok else 0.0)
        add_measurement(st, f"{p['regulator']}_Iload_a", i)

        if sel_active:
            set_system_state(st, "failed")
            add_failed(st, p["regulator"])
            add_event(st, "SEL_latched")
        elif not parity_ok:
            set_system_state(st, "degraded")
            add_event(st, "SEU_bit_flip")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev = self.params["bg_rad_uSv_h"]
