"""Fatigue cycling: many small mechanical cycles accumulate damage. Damage is
linear in cycle count (single-point Miner's rule). Joint fails at exactly
`cycles_to_failure` cycles → tick = cycles_to_failure / (cycle_freq_hz * dt).
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


class FatigueCycling(Scenario):
    name = "fatigue_cycling"
    description = "Miner's-rule fatigue under steady cycling."

    dt = 0.05
    default_max_ticks = 1200  # 60 s

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "strain_gauge": "SG1",
            "joint_id": "J7",
            "cycle_freq_hz": 5.0,
            "strain_amp_microstrain": 800.0,
            "cycles_to_failure": 220,
            "noise_sigma": 4.0,
            **params,
        }
        self._prev = 0.0

    def _fail_tick(self) -> int:
        p = self.params
        if p["cycle_freq_hz"] <= 0:
            return self.max_ticks + 1
        return int(round(p["cycles_to_failure"] / (p["cycle_freq_hz"] * self.dt)))

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        tf = self._fail_tick()
        if self.tick < tf:
            phase = 2.0 * math.pi * p["cycle_freq_hz"] * ts
            clean = p["strain_amp_microstrain"] * math.copysign(1.0, math.sin(phase))
        else:
            clean = 0.0  # joint debonded
        v = clean + gaussian(rng, p["noise_sigma"])
        rate = (clean - self._prev) / self.dt
        self._prev = clean

        add_sensor(st, reading(
            p["strain_gauge"], "mechanical",
            value=v, rate=rate, units="microstrain",
            threshold=p["strain_amp_microstrain"] * 1.5,
            nominal=p["strain_amp_microstrain"],
        ))
        add_component(st, comp(p["strain_gauge"], "strain_gauge"))

        cycles_done = p["cycle_freq_hz"] * ts
        damage_frac = min(1.0, cycles_done / max(1.0, p["cycles_to_failure"]))
        joint_state = "failed" if self.tick >= tf else (
            "degraded" if damage_frac > 0.7 else "nominal")
        joint_mode = "fatigue_crack" if joint_state == "failed" else (
            "fatigue_damage" if joint_state == "degraded" else "")
        add_component(st, comp(p["joint_id"], "solder_joint",
                               state=joint_state, degradation_mode=joint_mode))

        add_measurement(st, "cycles_accumulated", cycles_done)
        add_measurement(st, "damage_fraction", damage_frac)
        if self.tick >= tf:
            set_system_state(st, "failed")
            add_failed(st, p["joint_id"])
            add_event(st, "fatigue_crack")
        elif damage_frac > 0.7:
            set_system_state(st, "degraded")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev = 0.0
