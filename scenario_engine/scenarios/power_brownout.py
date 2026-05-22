"""
scenario_engine.scenarios.power_brownout

Voltage rail sags below nominal. Components on the shared rail
co-degrade. Different components have different brownout tolerances.

V_3V3 nominal: 3.30V
Sag begins tick 10, reaches minimum 2.85V at tick 60.

Components U1 (logic, needs >3.0V), U2 (analog, needs >3.1V),
U3 (sensor, needs >2.9V) react at different thresholds.

AI must:
  - Detect rail sag from voltage sensor
  - Predict which components will fail first
  - Decide intervention: shed load, switch to backup rail,
    or accept degradation in non-critical components

Interventions accepted:
  - "shed_load_U2"  → U2 disconnected, rail recovers partial
  - "switch_backup_rail"  → rail clamped to 3.25V
  - "shed_load_U1" / "shed_load_U3"  → similar
  - "ignore" → no intervention
"""

from .base import Scenario, ScenarioState


class PowerBrownout(Scenario):
    name = "power_brownout"
    description = (
        "V_3V3 rail sags. U1/U2/U3 degrade at different voltages. "
        "AI must triage load shedding."
    )

    def __init__(self, seed: int = 0, max_ticks: int = 200):
        super().__init__(seed=seed, max_ticks=max_ticks)
        self.V_nominal = 3.30
        self.V_min = 2.85
        self.sag_start = 10
        self.sag_complete = 60
        self.recovery_start = 150  # natural recovery if no fault

        # Components on the rail
        self.components_spec = {
            "U1": {"V_threshold": 3.00, "type": "logic_CMOS", "load_a": 0.20},
            "U2": {"V_threshold": 3.10, "type": "analog_opamp", "load_a": 0.05},
            "U3": {"V_threshold": 2.90, "type": "sensor_I2C", "load_a": 0.08},
        }
        self.shed = set()
        self.backup_active = False
        self.intervention_tick = None

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        self.intervention_tick = tick
        if "shed_load" in a or "shed" in a:
            for cid in self.components_spec:
                if cid.lower() in a:
                    self.shed.add(cid)
                    return
        if "backup" in a or "switch" in a:
            self.backup_active = True
            return

    def _rail_voltage(self) -> float:
        if self.backup_active and self.intervention_tick is not None and self.tick >= self.intervention_tick:
            return 3.25
        # Sag profile
        if self.tick < self.sag_start:
            v = self.V_nominal
        elif self.tick < self.sag_complete:
            frac = (self.tick - self.sag_start) / (self.sag_complete - self.sag_start)
            v = self.V_nominal - (self.V_nominal - self.V_min) * frac
        elif self.tick < self.recovery_start:
            v = self.V_min
        else:
            frac = min((self.tick - self.recovery_start) / 30.0, 1.0)
            v = self.V_min + (self.V_nominal - self.V_min) * frac

        # Shedding reduces load, raises voltage
        total_load = sum(
            spec["load_a"] for cid, spec in self.components_spec.items()
            if cid not in self.shed
        )
        nominal_load = sum(spec["load_a"] for spec in self.components_spec.values())
        if nominal_load > 0:
            load_factor = total_load / nominal_load
            # Each 10% load reduction recovers ~0.04V
            v += (1.0 - load_factor) * 0.4

        return max(v, 2.5)

    def _component_state(self, cid: str, v: float) -> str:
        if cid in self.shed:
            return "offline"
        threshold = self.components_spec[cid]["V_threshold"]
        if v >= threshold:
            return "nominal"
        elif v >= threshold - 0.15:
            return "degraded"
        else:
            return "failed"

    def step(self) -> ScenarioState:
        v = self._rail_voltage()

        # Compute total current
        total_current = sum(
            spec["load_a"] for cid, spec in self.components_spec.items()
            if cid not in self.shed
        )

        sensors = {
            "power_V_3V3": {
                "component_id": "V_3V3_rail",
                "sensor_type": "power",
                "value": round(v, 3),
                "rate": 0.0,  # could compute, leave 0 for simplicity
                "units": "V",
                "threshold": 2.90,  # below this → multi-component risk
                "nominal": self.V_nominal,
            },
            "power_I_3V3": {
                "component_id": "V_3V3_rail",
                "sensor_type": "current",
                "value": round(total_current, 3),
                "rate": 0.0,
                "units": "A",
                "threshold": 0.50,
                "nominal": 0.33,
            },
        }

        components = {}
        worst_state = "stable"
        for cid in self.components_spec:
            state = self._component_state(cid, v)
            components[cid] = {
                "component_type": self.components_spec[cid]["type"],
                "state": state,
                "degradation_mode": "undervoltage" if state in ("degraded", "failed") else "",
            }
            if state == "failed" and worst_state != "failed":
                worst_state = "failed"
            elif state == "degraded" and worst_state == "stable":
                worst_state = "degraded"

        actual_outcome = {
            "V_3V3": round(v, 3),
            "system_state": worst_state,
        }
        for cid in self.components_spec:
            actual_outcome[f"{cid}_state"] = self._component_state(cid, v)

        state = ScenarioState(
            tick=self.tick,
            timestamp=float(self.tick),
            sensors=sensors,
            components=components,
            actual_outcome=actual_outcome,
        )
        self.tick += 1
        return state
