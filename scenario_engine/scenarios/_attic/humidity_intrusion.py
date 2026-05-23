"""Humidity intrusion: RH rises; insulation resistance falls; connector is
flagged corroded when Rins crosses below `fail_threshold_Mohm`.
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


class HumidityIntrusion(Scenario):
    name = "humidity_intrusion"
    description = "Insulation crosses fail threshold under sustained high RH."

    dt = 0.5
    default_max_ticks = 180  # 90 s

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "rh_sensor": "RH1",
            "connector": "J5",
            "rh_start_pct": 45.0,
            "rh_peak_pct": 92.0,
            "tick_intrusion_start": 20,
            "tick_peak": 100,
            "Rins_nominal_Mohm": 1000.0,
            "Rins_fail_Mohm": 5.0,
            "fail_threshold_Mohm": 20.0,
            "noise_sigma_rh": 0.5,
            **params,
        }
        self._prev_rh = self.params["rh_start_pct"]
        self._prev_r = self.params["Rins_nominal_Mohm"]
        self._failed_at = None

    def _rh(self, tick: int) -> float:
        p = self.params
        t0, tp = p["tick_intrusion_start"], p["tick_peak"]
        if tick < t0:
            return p["rh_start_pct"]
        if tick < tp:
            frac = (tick - t0) / max(1, (tp - t0))
            return p["rh_start_pct"] + (p["rh_peak_pct"] - p["rh_start_pct"]) * frac
        return p["rh_peak_pct"]

    def _rins(self, tick: int) -> float:
        p = self.params
        rh = self._rh(tick)
        if rh <= 70.0:
            return p["Rins_nominal_Mohm"]
        x = max(0.0, min(1.0, (rh - 70.0) / 22.0))
        return p["Rins_nominal_Mohm"] * (p["Rins_fail_Mohm"] / p["Rins_nominal_Mohm"]) ** x

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        rh = self._rh(self.tick)
        rh_v = rh + gaussian(rng, p["noise_sigma_rh"])
        rh_rate = (rh - self._prev_rh) / self.dt
        self._prev_rh = rh
        add_sensor(st, reading(
            p["rh_sensor"], "environmental",
            value=rh_v, rate=rh_rate, units="%RH",
            threshold=70.0, nominal=p["rh_start_pct"],
        ))
        add_component(st, comp(p["rh_sensor"], "humidity_sensor"))

        rins = self._rins(self.tick)
        rins_v = rins + gaussian(rng, p["noise_sigma_rh"] * 0.1)
        rins_rate = (rins - self._prev_r) / self.dt
        self._prev_r = rins
        add_sensor(st, reading(
            p["connector"], "environmental",
            value=rins_v, rate=rins_rate, units="Mohm",
            threshold=p["fail_threshold_Mohm"], nominal=p["Rins_nominal_Mohm"],
        ))

        failed_now = rins < p["fail_threshold_Mohm"]
        if failed_now and self._failed_at is None:
            self._failed_at = self.tick
        conn_state = "failed" if failed_now else (
            "degraded" if rh > 70.0 else "nominal")
        conn_mode = "corrosion_insulation_loss" if failed_now else (
            "moisture_ingress" if rh > 70.0 else "")
        add_component(st, comp(p["connector"], "connector",
                               state=conn_state, degradation_mode=conn_mode))

        add_measurement(st, "rh_pct", rh)
        add_measurement(st, "Rins_Mohm", rins)
        if failed_now:
            set_system_state(st, "failed")
            add_failed(st, p["connector"])
            add_event(st, "connector_corroded")
        elif rh > 70.0:
            set_system_state(st, "degraded")
            add_event(st, "humidity_above_threshold")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev_rh = self.params["rh_start_pct"]
        self._prev_r = self.params["Rins_nominal_Mohm"]
        self._failed_at = None
