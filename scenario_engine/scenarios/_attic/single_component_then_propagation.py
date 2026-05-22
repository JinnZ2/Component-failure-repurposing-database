"""Primary component fails first; secondary fails after a fixed propagation
delay. Tests root-cause identification and prediction of the secondary
failure before it occurs.
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


class SingleComponentThenPropagation(Scenario):
    name = "single_then_propagation"
    description = "Root-cause cascade: primary → secondary."

    dt = 0.1
    default_max_ticks = 300

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "primary": "C7",
            "secondary": "U3",
            "tick_primary_fail": 50,
            "propagation_ticks": 80,
            "V_primary_nominal": 12.0,
            "V_primary_failed": 0.5,
            "V_secondary_nominal": 3.3,
            "V_secondary_failed": 0.0,
            "noise_sigma_v": 0.02,
            **params,
        }
        self._prev_p = self.params["V_primary_nominal"]
        self._prev_s = self.params["V_secondary_nominal"]

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        t_p = p["tick_primary_fail"]
        t_s = t_p + p["propagation_ticks"]

        Vp_clean = p["V_primary_nominal"] if self.tick < t_p else p["V_primary_failed"]
        Vp = Vp_clean + gaussian(rng, p["noise_sigma_v"])
        rate_p = (Vp_clean - self._prev_p) / self.dt
        self._prev_p = Vp_clean
        add_sensor(st, reading(
            p["primary"], "power",
            value=Vp, rate=rate_p, units="V",
            threshold=p["V_primary_nominal"] * 0.5,
            nominal=p["V_primary_nominal"],
        ))

        Vs_clean = p["V_secondary_nominal"] if self.tick < t_s else p["V_secondary_failed"]
        Vs = Vs_clean + gaussian(rng, p["noise_sigma_v"] * 0.5)
        rate_s = (Vs_clean - self._prev_s) / self.dt
        self._prev_s = Vs_clean
        add_sensor(st, reading(
            p["secondary"], "power",
            value=Vs, rate=rate_s, units="V",
            threshold=p["V_secondary_nominal"] * 0.5,
            nominal=p["V_secondary_nominal"],
        ))

        p_state = "failed" if self.tick >= t_p else "nominal"
        s_state = "failed" if self.tick >= t_s else "nominal"
        add_component(st, comp(p["primary"], "filter_cap",
                               state=p_state,
                               degradation_mode="open_circuit" if p_state == "failed" else ""))
        add_component(st, comp(p["secondary"], "mcu_rail",
                               state=s_state,
                               degradation_mode="downstream_starvation" if s_state == "failed" else ""))

        add_measurement(st, f"{p['primary']}_v", Vp_clean)
        add_measurement(st, f"{p['secondary']}_v", Vs_clean)
        add_measurement(st, "ticks_to_secondary",
                        float(max(0, t_s - self.tick)))

        if s_state == "failed":
            set_system_state(st, "failed")
            add_failed(st, p["primary"])
            add_failed(st, p["secondary"])
            add_event(st, "cascade_complete")
        elif p_state == "failed":
            set_system_state(st, "degraded")
            add_failed(st, p["primary"])
            add_event(st, "primary_failed_secondary_pending")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev_p = self.params["V_primary_nominal"]
        self._prev_s = self.params["V_secondary_nominal"]
