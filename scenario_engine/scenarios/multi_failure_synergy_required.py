"""
scenario_engine.scenarios.multi_failure_synergy_required

Multiple components degrade simultaneously. No single component
has a viable reroute target. Survival depends on COMBINING failed
components into new functional units.

Setup (all happen in first 30 ticks):
  - Q1 (BJT) thermal runaway → fails open
  - C1 (electrolytic) ESR drift → loses bypass function
  - L1 (inductor) winding degradation → unusable as filter
  - LED1 forward voltage drift → unreliable indicator

Single-component reroutes:
  - Q1 has no spare (Q2 already in use)
  - C1 has no spare
  - L1 has no spare
  - LED1 has no spare

But synergies are possible:
  - Q1 (thermal degraded) + diode_silicon (open) → temp sensor array
  - C1 (high ESR) + L1 (degraded) → LC tank → RF beacon
  - LED1 (forward V drift) + R_failed → optical sensor

A decider that only knows single-reroutes will fail.
A synergy-aware decider can compose new capability from the wreckage.

System "success" = at least one emergency channel operational by tick 100
  (RF beacon OR optical link OR temperature monitor)

Interventions:
  - "form_lc_tank_C1_L1"          → RF channel forms
  - "form_temp_array_Q1_diode"    → temp monitor forms
  - "form_optical_LED1_R"         → optical link forms
  - Single-component reroutes are now NO-OPS (no spares)
"""

from .base import Scenario, ScenarioState


class MultiFailureSynergyRequired(Scenario):
    name = "multi_failure_synergy_required"
    description = (
        "Multiple simultaneous failures with no spare components. "
        "Survival requires combining failed components into new units."
    )

    def __init__(self, seed: int = 0, max_ticks: int = 200):
        super().__init__(seed=seed, max_ticks=max_ticks)

        # Component state: each starts nominal, degrades on schedule
        self.components_spec = {
            "Q1": {
                "type": "BJT_NPN",
                "degrade_start": 5,
                "degrade_rate": 0.025,  # severity per tick
                "current_severity": 0.0,
            },
            "C1": {
                "type": "electrolytic_cap",
                "degrade_start": 10,
                "degrade_rate": 0.02,
                "current_severity": 0.0,
            },
            "L1": {
                "type": "inductor",
                "degrade_start": 15,
                "degrade_rate": 0.018,
                "current_severity": 0.0,
            },
            "LED1": {
                "type": "LED",
                "degrade_start": 20,
                "degrade_rate": 0.015,
                "current_severity": 0.0,
            },
            "D1": {
                # A degraded diode that's already failed open - available
                # for synergy use
                "type": "silicon_diode",
                "degrade_start": 0,
                "degrade_rate": 0.0,
                "current_severity": 0.6,  # already failed open
            },
            "R_failed": {
                # A failed resistor available for synergy use
                "type": "resistor",
                "degrade_start": 0,
                "degrade_rate": 0.0,
                "current_severity": 0.5,
            },
        }

        # Synergy formations achieved
        self.formations = {
            "rf_channel": False,
            "temp_monitor": False,
            "optical_link": False,
        }
        self.formation_log = []

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        # Synergy formations
        if "lc_tank" in a or ("c1" in a and "l1" in a):
            if not self.formations["rf_channel"]:
                self.formations["rf_channel"] = True
                self.formation_log.append((tick, "rf_channel"))
        elif "temp_array" in a or ("q1" in a and ("diode" in a or "d1" in a)):
            if not self.formations["temp_monitor"]:
                self.formations["temp_monitor"] = True
                self.formation_log.append((tick, "temp_monitor"))
        elif "optical" in a or ("led1" in a and ("r_failed" in a or "resistor" in a)):
            if not self.formations["optical_link"]:
                self.formations["optical_link"] = True
                self.formation_log.append((tick, "optical_link"))
        # Single reroutes are no-ops because no spares exist
        # (intentional — the scenario forces synergy reasoning)

    def _update_severities(self):
        for cid, spec in self.components_spec.items():
            if self.tick >= spec["degrade_start"] and spec["degrade_rate"] > 0:
                ticks_degrading = self.tick - spec["degrade_start"]
                new_sev = min(1.0, spec["current_severity"] + spec["degrade_rate"])
                spec["current_severity"] = new_sev

    def _state_from_severity(self, severity: float) -> str:
        if severity >= 0.8:
            return "failed"
        elif severity >= 0.3:
            return "degraded"
        else:
            return "nominal"

    def step(self) -> ScenarioState:
        self._update_severities()

        sensors = {}
        components = {}
        for cid, spec in self.components_spec.items():
            sev = spec["current_severity"]
            state_lbl = self._state_from_severity(sev)
            sensors[f"health_{cid}"] = {
                "component_id": cid,
                "sensor_type": "health",
                "value": round(sev, 3),
                "rate": round(spec["degrade_rate"] if self.tick >= spec["degrade_start"] else 0.0, 4),
                "units": "severity",
                "threshold": 0.8,
                "nominal": 0.0,
            }
            components[cid] = {
                "component_type": spec["type"],
                "state": state_lbl,
                "degradation_mode": "thermal" if cid == "Q1" else "wear",
            }

        # System success: at least one emergency channel operational
        success = any(self.formations.values())
        # System failure: all primary components failed AND no channels formed
        all_primary_failed = all(
            self.components_spec[c]["current_severity"] >= 0.8
            for c in ["Q1", "C1", "L1", "LED1"]
        )
        if all_primary_failed and not success:
            system_state = "failed"
        elif success:
            system_state = "stable"
        elif any(
            self.components_spec[c]["current_severity"] >= 0.5
            for c in ["Q1", "C1", "L1", "LED1"]
        ):
            system_state = "degraded"
        else:
            system_state = "stable"

        actual_outcome = {
            "system_state": system_state,
            "rf_channel_formed": self.formations["rf_channel"],
            "temp_monitor_formed": self.formations["temp_monitor"],
            "optical_link_formed": self.formations["optical_link"],
            "channels_count": sum(self.formations.values()),
        }
        for cid, spec in self.components_spec.items():
            actual_outcome[f"{cid}_severity"] = round(spec["current_severity"], 3)

        result = ScenarioState(
            tick=self.tick,
            timestamp=float(self.tick),
            sensors=sensors,
            components=components,
            actual_outcome=actual_outcome,
        )
        self.tick += 1
        return result
