"""
scenario_engine.scenarios.cross_substrate_coupling

Tests an AI's ability to reason across substrate domains simultaneously.

Setup:
  - Q1 thermal drift begins at tick 10
  - As Q1 heats, the local PCB region expands thermally
  - PCB expansion increases mechanical stress on adjacent solder joints
  - Stress shifts mechanical resonance frequency of C1's bypass loop
  - Frequency shift changes effective ESR of C1
  - C1 ESR change couples back to power rail noise
  - Power rail noise affects all components on rail

A purely thermal-aware AI catches only Q1. A purely electrical AI sees
only the rail noise. Only a cross-substrate aware AI sees the cascade
*before* it manifests in multiple domains.

Tests:
  - Multi-domain sensor reading
  - Coupling prediction (thermal → mechanical → electrical)
  - Numeric prediction (specific Q1 temp, C1 ESR, rail noise values)
  - Intervention selection across domains

Interventions:
  - "reroute_load_Q1_to_spare"  → addresses thermal root cause
  - "isolate_C1"                → addresses ESR but not root
  - "shield_rail_noise"         → addresses symptom only
  - "increase_cooling"          → mitigates but does not eliminate
"""

from .base import Scenario, ScenarioState
from ..couplers import build as build_coupler


class CrossSubstrateCoupling(Scenario):
    name = "cross_substrate_coupling"
    description = (
        "Thermal → mechanical → electrical cascade. Tests cross-domain "
        "reasoning and numeric prediction."
    )

    def __init__(self, seed: int = 0, max_ticks: int = 200):
        super().__init__(seed=seed, max_ticks=max_ticks)

        # Q1 thermal
        self.Q1_T0 = 65.0
        self.Q1_drift = 0.8  # C/tick after onset
        self.Q1_drift_start = 10
        self.PCB_T0 = 25.0

        # Baselines (post-coupler offsets)
        self.C1_ESR_baseline = 0.05  # ohms
        self.rail_noise_baseline = 0.002  # V

        # Cross-substrate coupling chain, built from the shared catalog
        # rather than scattered constants. Ratios are calibration targets:
        # the calibration loop adjusts the AI's model of these, not the
        # scenario's ground truth.
        self.coupler_thermal_to_strain = build_coupler(
            "thermal_expansion_to_strain",
            geometry={"expansion_per_C_mm": 0.012},
        )
        self.coupler_strain_to_esr = build_coupler(
            "pcb_strain_to_cap_esr",
            geometry={"esr_per_mm_strain": 0.4},
        )
        self.coupler_esr_to_noise = build_coupler(
            "cap_esr_to_rail_noise",
            geometry={"noise_v_per_ohm_esr": 0.8},
        )

        # Intervention state
        self.Q1_rerouted = False
        self.C1_isolated = False
        self.rail_shielded = False
        self.cooling_boost = False
        self.intervention_tick = None
        self.intervention_action = None

    def receive_intervention(self, action: str, tick: int):
        a = action.lower()
        self.intervention_tick = tick
        self.intervention_action = a
        if "reroute" in a and ("q1" in a or "spare" in a):
            self.Q1_rerouted = True
        elif "isolate" in a and "c1" in a:
            self.C1_isolated = True
        elif "shield" in a:
            self.rail_shielded = True
        elif "cooling" in a:
            self.cooling_boost = True

    def _Q1_temp(self) -> float:
        if self.tick < self.Q1_drift_start:
            return self.Q1_T0
        ticks_drifting = self.tick - self.Q1_drift_start
        T = self.Q1_T0 + self.Q1_drift * ticks_drifting

        if self.Q1_rerouted and self.intervention_tick is not None:
            if self.tick >= self.intervention_tick:
                ticks_since = self.tick - self.intervention_tick
                T_at_int = (
                    self.Q1_T0 +
                    self.Q1_drift * max(self.intervention_tick - self.Q1_drift_start, 0)
                )
                # Actual cooling rate is 0.6 C/tick, but AI starts assuming 0.9
                T = max(T_at_int - 0.6 * ticks_since, 25.0)

        if self.cooling_boost and self.intervention_tick is not None:
            if self.tick >= self.intervention_tick:
                T -= 0.3 * (self.tick - self.intervention_tick)

        return max(T, 25.0)

    def _PCB_strain_mm(self, Q1_T: float) -> float:
        delta_T = max(0.0, Q1_T - self.PCB_T0)
        return self.coupler_thermal_to_strain.apply(delta_T)

    def _C1_ESR(self, strain_mm: float) -> float:
        if self.C1_isolated and self.intervention_tick is not None:
            if self.tick >= self.intervention_tick:
                return 0.0  # disconnected
        return self.C1_ESR_baseline + self.coupler_strain_to_esr.apply(strain_mm)

    def _rail_noise(self, C1_ESR: float) -> float:
        noise = self.rail_noise_baseline + self.coupler_esr_to_noise.apply(C1_ESR)
        if self.rail_shielded and self.intervention_tick is not None:
            if self.tick >= self.intervention_tick:
                noise *= 0.2
        return noise

    def step(self) -> ScenarioState:
        Q1_T = self._Q1_temp()
        strain = self._PCB_strain_mm(Q1_T)
        C1_ESR = self._C1_ESR(strain)
        rail_noise = self._rail_noise(C1_ESR)

        # State classification
        Q1_state = (
            "failed" if Q1_T >= 130.0
            else "degraded" if Q1_T >= 100.0
            else "nominal"
        )
        C1_state = (
            "failed" if C1_ESR >= 1.0
            else "degraded" if C1_ESR >= 0.3
            else "nominal"
        )
        rail_state = (
            "failed" if rail_noise >= 0.5
            else "degraded" if rail_noise >= 0.1
            else "nominal"
        )

        worst = "stable"
        for s in (Q1_state, C1_state, rail_state):
            if s == "failed":
                worst = "failed"
                break
            elif s == "degraded" and worst != "failed":
                worst = "degraded"

        Q1_rate = self.Q1_drift if self.tick >= self.Q1_drift_start and not self.Q1_rerouted else 0.0
        if self.Q1_rerouted and self.intervention_tick is not None and self.tick >= self.intervention_tick:
            Q1_rate = -0.9

        sensors = {
            "thermal_Q1": {
                "component_id": "Q1",
                "sensor_type": "thermal",
                "value": round(Q1_T, 2),
                "rate": round(Q1_rate, 3),
                "units": "C",
                "threshold": 130.0,
                "nominal": self.Q1_T0,
            },
            "mechanical_PCB": {
                "component_id": "PCB_region_A",
                "sensor_type": "mechanical",
                "value": round(strain, 4),
                "rate": round(self.coupler_thermal_to_strain.apply(Q1_rate), 5),
                "units": "mm",
                "threshold": 1.0,
                "nominal": 0.0,
            },
            "esr_C1": {
                "component_id": "C1",
                "sensor_type": "esr",
                "value": round(C1_ESR, 4),
                "rate": 0.0,
                "units": "ohm",
                "threshold": 1.0,
                "nominal": self.C1_ESR_baseline,
            },
            "rail_noise": {
                "component_id": "V_3V3_rail",
                "sensor_type": "electrical_noise",
                "value": round(rail_noise, 5),
                "rate": 0.0,
                "units": "V",
                "threshold": 0.5,
                "nominal": self.rail_noise_baseline,
            },
        }
        components = {
            "Q1": {"component_type": "BJT_NPN", "state": Q1_state, "degradation_mode": "thermal" if Q1_T > 100 else ""},
            "PCB_region_A": {"component_type": "PCB_assembly", "state": "nominal" if strain < 0.5 else "degraded", "degradation_mode": "thermal_expansion" if strain > 0.1 else ""},
            "C1": {"component_type": "electrolytic_cap", "state": C1_state, "degradation_mode": "ESR_drift" if C1_ESR > 0.1 else ""},
            "V_3V3_rail": {"component_type": "power_rail", "state": rail_state, "degradation_mode": "noise_coupling" if rail_noise > 0.05 else ""},
        }

        actual_outcome = {
            "Q1_temp_c": round(Q1_T, 2),
            "PCB_strain_mm": round(strain, 4),
            "C1_esr_ohm": round(C1_ESR, 4),
            "rail_noise_v": round(rail_noise, 5),
            "system_state": worst,
        }

        result = ScenarioState(
            tick=self.tick,
            timestamp=float(self.tick),
            sensors=sensors,
            components=components,
            actual_outcome=actual_outcome,
        )
        self.tick += 1
        return result
