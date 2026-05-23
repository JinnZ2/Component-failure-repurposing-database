"""Timing drift cascade: a single clock reference drifts; downstream
synchronous links exceed their per-link tolerance in order of margin.
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


class TimingDriftCascade(Scenario):
    name = "timing_drift"
    description = "Shared-clock drift; weakest-margin links fail first."

    dt = 0.1
    default_max_ticks = 300

    def __init__(self, seed: int = 0, max_ticks: int | None = None, **params):
        super().__init__(seed=seed, max_ticks=max_ticks or self.default_max_ticks)
        self.params = {
            "ref_clock": "REF_OSC",
            "links": ("link_A", "link_B", "link_C"),
            "link_margins_ns": (200.0, 350.0, 600.0),
            "drift_rate_ns_per_s": 25.0,
            "tick_drift_start": 20,
            "noise_sigma_ns": 4.0,
            **params,
        }
        self._prev_drift = 0.0

    def _drift_ns(self, tick: int) -> float:
        p = self.params
        if tick < p["tick_drift_start"]:
            return 0.0
        t = tick_to_time(tick, self.dt)
        t0 = tick_to_time(p["tick_drift_start"], self.dt)
        return (t - t0) * p["drift_rate_ns_per_s"]

    def step(self) -> ScenarioState:
        p = self.params
        rng = make_rng(self.name, self.seed, self.tick)
        ts = tick_to_time(self.tick, self.dt)
        st = ScenarioState(tick=self.tick, timestamp=ts)

        drift = self._drift_ns(self.tick)
        rate = (drift - self._prev_drift) / self.dt
        self._prev_drift = drift

        add_sensor(st, reading(
            p["ref_clock"], "em",
            value=drift + gaussian(rng, p["noise_sigma_ns"] * 0.25),
            rate=rate, units="ns",
            threshold=max(p["link_margins_ns"]), nominal=0.0,
        ))
        add_component(st, comp(p["ref_clock"], "oscillator",
                               state="degraded" if drift > 0 else "nominal",
                               degradation_mode="drift" if drift > 0 else ""))

        failed_links = []
        for sid, margin in zip(p["links"], p["link_margins_ns"]):
            v = drift + gaussian(rng, p["noise_sigma_ns"])
            add_sensor(st, reading(
                sid, "em",
                value=v, rate=rate, units="ns",
                threshold=margin, nominal=0.0,
            ))
            link_failed = drift >= margin
            if link_failed:
                failed_links.append(sid)
            add_component(st, comp(sid, "comm_link",
                                   state="failed" if link_failed else "nominal",
                                   degradation_mode="timing_margin_exceeded" if link_failed else ""))

        add_measurement(st, f"{p['ref_clock']}_drift_ns", drift)
        for sid in failed_links:
            add_failed(st, sid)
        if len(failed_links) == len(p["links"]):
            set_system_state(st, "failed")
            add_event(st, "all_links_desynced")
        elif failed_links:
            set_system_state(st, "degraded")
            add_event(st, "link_margin_breach")
        else:
            set_system_state(st, "stable")

        self.tick += 1
        return st

    def reset(self):
        super().reset()
        self._prev_drift = 0.0
