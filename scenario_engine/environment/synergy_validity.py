"""
scenario_engine.environment.synergy_validity

Environmental conditions can invalidate or improve synergy proposals.

Examples (from physics, not narrative):
  - LC tank pairings degrade above 85°C (electrolytic dryout)
  - Optical pairings degrade in high humidity (condensation)
  - Thermal sensor arrays need stable ambient (drift compensation)
  - Mechanical pairings sensitive to high vibration

This module provides validity gates that a synergy-aware decider
can consult before forming a pairing. Falsifiable: each gate has
explicit thresholds.
"""

from typing import Dict, Any, List, Optional, Tuple


# Gates: (synergy_keyword, condition_check, reason_if_failed)
# condition_check: callable(env_state) -> bool (True = passes)

def _lc_tank_gate(env) -> Tuple[bool, str]:
    if env.temp_c > 85.0:
        return False, f"electrolytic dryout above 85°C (current: {env.temp_c}°C)"
    if env.memory.thermal_cycles > 50:
        return True, f"WARNING: {env.memory.thermal_cycles} thermal cycles accumulated"
    return True, "nominal"


def _optical_gate(env) -> Tuple[bool, str]:
    if env.humidity_pct > 90.0:
        return False, f"condensation risk at {env.humidity_pct}% RH"
    if env.contamination > 0.7:
        return False, f"contamination {env.contamination:.2f} blocks optical path"
    if env.memory.humidity_exposure_seconds > 7200:
        return True, "WARNING: extended humidity exposure"
    return True, "nominal"


def _thermal_array_gate(env) -> Tuple[bool, str]:
    # Thermal sensors need stable ambient for differential
    if env.memory.thermal_cycles > 20:
        return False, (f"thermal cycling ({env.memory.thermal_cycles}) "
                       "destroys calibration baseline")
    if env.vibration_g > 1.5:
        return False, f"vibration {env.vibration_g}g exceeds sensor stability"
    return True, "nominal"


def _mechanical_gate(env) -> Tuple[bool, str]:
    if env.vibration_g > 3.0:
        return False, f"vibration {env.vibration_g}g exceeds mechanical limits"
    if env.memory.vibration_dose > 100:
        return True, "WARNING: high cumulative vibration dose"
    return True, "nominal"


def _rf_beacon_gate(env) -> Tuple[bool, str]:
    if env.contamination > 0.8:
        return False, "antenna detuned by contamination"
    return True, "nominal"


SYNERGY_GATES = {
    "lc_tank": _lc_tank_gate,
    "rf_oscillator": _lc_tank_gate,
    "rf_fallback": _lc_tank_gate,
    "rf_beacon": _rf_beacon_gate,
    "optical": _optical_gate,
    "thermal_sensing_array": _thermal_array_gate,
    "temperature_compensated_sensor": _thermal_array_gate,
    "distributed_temp_measurement": _thermal_array_gate,
    "mechanical": _mechanical_gate,
    "vibration": _mechanical_gate,
}


def evaluate_synergy(env, synergy_effect: str,
                     repurpose_application: str = "") -> Dict[str, Any]:
    """
    Check whether a synergy proposal is viable under current environment.

    Returns:
      {
        "viable": bool,
        "reason": str,
        "warnings": [str],
        "gate_matched": str | None,
        "acceleration_factor": float
      }
    """
    text = (synergy_effect + " " + repurpose_application).lower()
    matched_gates = []
    for keyword, gate in SYNERGY_GATES.items():
        if keyword in text:
            matched_gates.append((keyword, gate))

    if not matched_gates:
        # No gate matches; assume nominal viability
        return {
            "viable": True,
            "reason": "no env gates apply",
            "warnings": [],
            "gate_matched": None,
            "acceleration_factor": env.acceleration_factor(),
        }

    # Evaluate all matched gates; any False makes overall False
    overall_viable = True
    reasons = []
    warnings_list = []
    for keyword, gate in matched_gates:
        viable, reason = gate(env)
        if not viable:
            overall_viable = False
            reasons.append(f"[{keyword}] {reason}")
        elif "WARNING" in reason:
            warnings_list.append(f"[{keyword}] {reason}")

    return {
        "viable": overall_viable,
        "reason": "; ".join(reasons) if reasons else "nominal",
        "warnings": warnings_list,
        "gate_matched": [k for k, _ in matched_gates],
        "acceleration_factor": env.acceleration_factor(),
    }
