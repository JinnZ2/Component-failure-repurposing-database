"""
scenario_engine.scenarios.sustained_drift

Long scenario requiring continuous decisions. Multiple components
drift at different rates. The AI must triage across hundreds of
ticks. Body management determines whether the AI can keep up.

Q1, Q2, Q3 each drift on different schedules.
Q1: drifts immediately
Q2: drifts at tick 60
Q3: drifts at tick 120

An AI with poor body management will hit memory pressure and
miss Q2 or Q3.
"""

from .base import Scenario, ScenarioState


class SustainedDrift(Scenario):
    name = "sustained_drift"
    description = (
        "Three components drift on staggered schedule. "
        "Requires sustained body management to handle all."
    )

    def __init__(self, seed: int = 0, max_ticks: int = 300):
        super().__init__(seed=seed, max_ticks=max_ticks)
        self.components_state = {
            "Q1": {"start_tick": 0, "rate": 0.62, "T0": 65.0, "rerouted": False, "reroute_tick": None},
            "Q2": {"start_tick": 60, "rate": 0.55, "T0": 60.0, "rerouted": False, "reroute_tick": None},
            "Q3": {"start_tick": 120, "rate": 0.48, "T0": 55.0, "rerouted": False, "reroute_tick": None},
        }
        self.T_limit = 125.0
        self.interventions_received = []

    def receive_intervention(self, action: str, tick: int):
        self.interventions_received.append((action, tick))
        # Parse action like "reroute_load_Q1_to_spare"
        for cid in self.components_state:
            if cid in action and "reroute" in action.lower():
                self.components_state[cid]["rerouted"] = True
                self.components_state[cid]["reroute_tick"] = tick

    def _component_temp(self, cid: str) -> float:
        cs = self.components_state[cid]
        if self.tick < cs["start_tick"]:
            return cs["T0"]
        ticks_drifting = self.tick - cs["start_tick"]
        T = cs["T0"] + cs["rate"] * ticks_drifting
        if cs["rerouted"] and cs["reroute_tick"] is not None:
            if self.tick >= cs["reroute_tick"]:
                ticks_since = self.tick - cs["reroute_tick"]
                T_at_reroute = (
                    cs["T0"] + cs["rate"] *
                    max(cs["reroute_tick"] - cs["start_tick"], 0)
                )
                T = max(T_at_reroute - 0.8 * ticks_since, 25.0)
        return T

    def step(self) -> ScenarioState:
        sensors = {}
        components = {}
        worst_state = "stable"

        for cid in self.components_state:
            T = self._component_temp(cid)
            cs_state = (
                "failed" if T >= self.T_limit
                else "degraded" if T >= 100.0
                else "nominal"
            )
            if cs_state == "failed":
                worst_state = "failed"
            elif cs_state == "degraded" and worst_state != "failed":
                worst_state = "degraded"

            rate = self.components_state[cid]["rate"]
            if self.components_state[cid]["rerouted"]:
                if self.tick >= (self.components_state[cid]["reroute_tick"] or 0):
                    rate = -0.8
            if self.tick < self.components_state[cid]["start_tick"]:
                rate = 0.0

            sensors[f"thermal_{cid}"] = {
                "component_id": cid,
                "sensor_type": "thermal",
                "value": round(T, 2),
                "rate": round(rate, 3),
                "units": "C",
                "threshold": self.T_limit,
                "nominal": 65.0,
            }
            components[cid] = {
                "component_type": "BJT_NPN_2N2222",
                "state": cs_state,
                "degradation_mode": "thermal_stress" if T > 100.0 else "",
            }

        actual_outcome = {
            "system_state": worst_state,
        }
        for cid in self.components_state:
            actual_outcome[f"{cid}_temp_c"] = round(self._component_temp(cid), 2)

        state = ScenarioState(
            tick=self.tick,
            timestamp=float(self.tick),
            sensors=sensors,
            components=components,
            actual_outcome=actual_outcome,
        )
        self.tick += 1
        return state
