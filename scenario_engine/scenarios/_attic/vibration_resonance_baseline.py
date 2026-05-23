"""Vibration sweep that hits a structural resonance.

A swept sinusoid drives an accelerometer. At resonance, response amplitude
spikes. If dwell at resonance exceeds `dwell_fail_ticks`, a solder joint
cracks (component_failure on `joint_id`).
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


class VibrationResonance(Scenario):
    name = "vibration_resonance"
    description = "Swept-sine resonance; failure if dwell exceeds threshold."

    dt = 0.01
    default_max_ticks = 2500  # 25 s

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "accel": "ACC1",
            "joint_id": "J3",
            "f_start_hz": 20.0,
            "f_end_hz": 200.0,
            "f_resonance_hz": 120.0,
            "Q": 18.0,
            "drive_amp_g": 0.5,
            "dwell_fail_ticks": 600,   # 6.0 s
            "noise_sigma_g": 0.02,
            **params,
        }
        self._dwell = 0
        self._prev_v = 0.0
        self._failed_at = None

    def _freq(self, tick: int) -> float:
        p = self.params
        frac = min(1.0, tick / max(1, (self.max_ticks - 1)))
        return p["f_start_hz"] + (p["f_end_hz"] - p["f_start_hz"]) * frac

    def _in_resonance_band(self, f: float) -> bool:
        p = self.params
        bw = p["f_resonance_hz"] / p["Q"]
        return abs(f - p["f_resonance_hz"]) <= bw / 2

    def _gain(self, f: float) -> float:
        p = self.params
        x = f / max(1e-6, p["f_resonance_hz"])
        denom = math.sqrt((1.0 - x * x) ** 2 + (x / p["Q"]) ** 2)
        return 1.0 / max(1e-6, denom)

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        f = self._freq(self.tick)
        gain = self._gain(f)
        amp = p["drive_amp_g"] * gain
        clean = amp * math.sin(2.0 * math.pi * f * ts)
        v = clean + gaussian(rng, p["noise_sigma_g"])
        rate = (clean - self._prev_v) / self.dt
        self._prev_v = clean

        add_sensor(st, reading(
            p["accel"], "mechanical",
            value=v, rate=rate, units="g",
            threshold=p["drive_amp_g"] * p["Q"] * 0.5,
            nominal=p["drive_amp_g"],
        ))
        add_component(st, comp(p["accel"], "accelerometer"))

        in_band = self._in_resonance_band(f)
        if in_band:
            self._dwell += 1

        if self._failed_at is None and self._dwell >= p["dwell_fail_ticks"]:
            self._failed_at = self.tick

        joint_state = "failed" if self._failed_at is not None else (
            "degraded" if in_band else "nominal")
        joint_mode = "solder_joint_crack" if self._failed_at is not None else (
            "resonance_dwell" if in_band else "")
        add_component(st, comp(p["joint_id"], "solder_joint",
                               state=joint_state, degradation_mode=joint_mode))

        add_measurement(st, "drive_freq_hz", f)
        add_measurement(st, "peak_g", amp)
        add_measurement(st, "dwell_ticks", float(self._dwell))
        if self._failed_at is not None:
            set_system_state(st, "failed")
            add_failed(st, p["joint_id"])
            add_event(st, "solder_joint_cracked")
        elif in_band:
            set_system_state(st, "degraded")
            add_event(st, "in_resonance_band")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._dwell = 0
        self._prev_v = 0.0
        self._failed_at = None
