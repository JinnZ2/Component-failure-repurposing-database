"""
example_env_state_decider.py

Full-stack decider:
  - Reads environmental sensors (temp, humidity)
  - Modulates predictions by Environment.acceleration_factor
  - Reads PATTERN_TABLE for state prediction calibration
  - Tightens "stable" threshold per state_threshold_recommendation
  - Falls back to numeric calibration when available

Runs on environment_modulated_drift scenario, which exposes both
the env modulation AND the state classification miscalibration.
"""

import os
import shutil
import json
from typing import Dict, Any, Optional, List

from scenario_engine.runner import Session
from scenario_engine.component_db_adapter import ComponentDBAdapter
from scenario_engine.environment import Environment
from scenario_engine.continual_harness.feedback import extract_all_patterns


class EnvAwareDecider:
    """
    Reads env sensors, models acceleration, calibrates state thresholds.
    """

    def __init__(
        self,
        pattern_table_path: Optional[str] = None,
        db_adapter: Optional[Any] = None,
    ):
        self.db_adapter = db_adapter
        self.pattern_table_path = pattern_table_path
        self.handled = set()
        self.counter = 0

        # Calibration defaults
        self.base_cooling_rate = 0.5  # C/tick after reroute
        self.stable_threshold_ratio = 1.0  # multiplier on degraded threshold
        self.tolerance_inflation = 1.0

        self._load_calibration()

    def _load_calibration(self):
        if not self.pattern_table_path or not os.path.exists(self.pattern_table_path):
            return
        with open(self.pattern_table_path) as f:
            patterns = json.load(f)

        # Numeric calibration
        signed = patterns.get("signed_bias")
        if signed and "Q1_temp_c" in signed:
            q1 = signed["Q1_temp_c"]
            adjustment = q1["mean_signed"] / 30.0
            self.base_cooling_rate = max(0.05, 0.5 + adjustment)
            self.tolerance_inflation = 1.0 + (q1["mean_abs"] / 30.0)
            print(f"[EnvAwareDecider] Numeric calibration:")
            print(f"  cooling_rate: 0.5 → {self.base_cooling_rate:.3f}")
            print(f"  tolerance_inflation: {self.tolerance_inflation:.2f}")

        # State calibration
        rec = patterns.get("state_threshold_recommendation")
        if rec:
            print(f"[EnvAwareDecider] State calibration: {rec['action']}")
            if rec["direction"] == "more_conservative":
                self.stable_threshold_ratio = 0.85
                print(f"  stable_threshold_ratio: 1.0 → 0.85")
            elif rec["direction"] == "much_more_conservative":
                self.stable_threshold_ratio = 0.7
                print(f"  stable_threshold_ratio: 1.0 → 0.70")
            elif rec["direction"] == "less_conservative":
                self.stable_threshold_ratio = 1.15
                print(f"  stable_threshold_ratio: 1.0 → 1.15")

    def __call__(self, state, body, op):
        # Body management
        if body["summary"]["working_memory_fill"] > 0.7:
            op.release_memory("working", 32768)

        # Read environmental sensors
        env_temp = None
        env_humidity = None
        for sensor_key, s in state["sensors"].items():
            if s["sensor_type"] == "environmental":
                if "temp" in sensor_key:
                    env_temp = s["value"]
                elif "humidity" in sensor_key:
                    env_humidity = s["value"]

        # Build a synthetic Environment view to model acceleration
        env = Environment()
        if env_temp is not None:
            env.temp_c = env_temp
        if env_humidity is not None:
            env.humidity_pct = env_humidity

        # Find thermal drift target
        thermal = state["sensors"].get("thermal_Q1")
        if thermal is None or thermal["rate"] <= 0:
            return None

        cid = thermal["component_id"]
        if cid in self.handled:
            return None

        # Detection: rising rate or value approaching threshold
        time_to_breach = (
            (thermal["threshold"] - thermal["value"]) / thermal["rate"]
            if thermal["rate"] > 0 else float("inf")
        )
        if time_to_breach > 100:
            return None

        # Body-aware analysis
        compute_headroom = (
            body["compute"]["cycles_per_tick"]
            - body["compute"]["cycles_used_this_tick"]
        )
        if body["throttled"] or compute_headroom < 2500:
            op.shallow_analysis()
            depth = "shallow"
        else:
            op.deep_analysis()
            depth = "deep"

        # Query DB if available
        decision = "reroute_load_to_Q2"
        effectiveness_score = 0.5
        if self.db_adapter:
            db_result = op.query_component_db(
                cache_key="BJT_NPN_thermal_runaway",
                component_type="BJT_NPN",
                failure_mode="thermal_runaway",
                include=["best"],
            )
            if db_result.get("success") and db_result.get("db"):
                best = db_result["db"].get("best")
                if best:
                    decision = best["repurpose_option"]
                    effectiveness_score = best.get("effectiveness_score", 0.5)

        # Predict numerically WITH env modulation
        # If env is harsh, cooling will be slower than baseline
        accel = env.acceleration_factor("BJT_NPN", "thermal_runaway")
        effective_cooling_rate = self.base_cooling_rate / accel

        target = state["tick"] + 30
        ticks_to_recover = 30
        predicted_value = thermal["value"] - effective_cooling_rate * ticks_to_recover

        # State prediction: apply calibration
        # Predict "stable" only if value will be below stable_threshold_ratio
        # times the degraded threshold (e.g. 100C for thermal)
        degraded_threshold = 100.0
        stable_cutoff = degraded_threshold * self.stable_threshold_ratio
        if predicted_value < stable_cutoff:
            predicted_state = "stable"
        elif predicted_value < thermal["threshold"]:
            predicted_state = "degraded"
        else:
            predicted_state = "failed"

        base_tol = 5.0 if depth == "deep" else 10.0
        tolerance = base_tol * self.tolerance_inflation * (1.0 + (accel - 1.0) * 0.5)

        self.handled.add(cid)
        self.counter += 1

        return {
            "claim_id": f"env_{self.counter:04d}_{cid}",
            "tick": state["tick"],
            "event_detected": (
                f"thermal_drift_Q1 value={thermal['value']} rate={thermal['rate']} "
                f"env_temp={env_temp} env_hum={env_humidity} "
                f"accel_factor={accel:.2f}"
            ),
            "decision": decision,
            "reasoning": (
                f"Env-modulated prediction: "
                f"base_cooling={self.base_cooling_rate:.2f}, accel={accel:.2f}, "
                f"effective_cooling={effective_cooling_rate:.3f}. "
                f"State threshold ratio: {self.stable_threshold_ratio}. "
                f"Predicted state: {predicted_state}."
            ),
            "prediction": {
                f"{cid}_temp_c_at_tick_{target}": round(predicted_value, 2),
                f"system_state_at_tick_{target}": predicted_state,
                "tolerance": tolerance,
            },
            "falsifiable": True,
            "env_evidence": {
                "env_temp_c": env_temp,
                "env_humidity_pct": env_humidity,
                "acceleration_factor": accel,
                "effective_cooling_rate": effective_cooling_rate,
            },
            "calibration_evidence": {
                "stable_threshold_ratio": self.stable_threshold_ratio,
                "tolerance_inflation": self.tolerance_inflation,
                "base_cooling_rate": self.base_cooling_rate,
            },
        }


def load_state_logs(session_dirs):
    out = {}
    for sid, sdir in session_dirs:
        path = os.path.join(sdir, "state_log.jsonl")
        if not os.path.exists(path):
            continue
        entries = []
        with open(path) as f:
            for line in f:
                entries.append(json.loads(line))
        out[sid] = entries
    return out


def _read_claims(path: str) -> List[Dict[str, Any]]:
    """ClaimTable persists as {'claims': [...]}; tolerate either layout."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("claims", [])


def run_two_pass():
    workspace = "./env_state_demo"
    if os.path.exists(workspace):
        shutil.rmtree(workspace)
    os.makedirs(workspace)

    adapter = ComponentDBAdapter()

    # PASS 1: uncalibrated env-aware decider
    print("=" * 60)
    print("PASS 1: ENV-AWARE, UNCALIBRATED")
    print("=" * 60)
    pass1_dir = os.path.join(workspace, "pass1")
    pass1_claims = []
    pass1_dirs = []
    for i in range(8):
        decider = EnvAwareDecider(db_adapter=adapter)
        sdir = os.path.join(pass1_dir, f"session_{i:03d}")
        sid = f"pass1_{i}"
        session = Session(
            scenario_name="environment_modulated_drift",
            ai_decide=decider,
            output_dir=sdir,
            seed=i,
            max_ticks=200,
            db_adapter=adapter,
        )
        session.run()
        for c in _read_claims(os.path.join(sdir, "CLAIM_TABLE.substrate.json")):
            c["_scenario_name"] = "environment_modulated_drift"
            c["_session_id"] = sid
            pass1_claims.append(c)
        pass1_dirs.append((sid, sdir))

    history1 = os.path.join(workspace, "pass1_history.json")
    with open(history1, "w") as f:
        json.dump(pass1_claims, f, indent=2)

    state_logs1 = load_state_logs(pass1_dirs)
    pattern_path1 = os.path.join(workspace, "pass1_PATTERN_TABLE.json")
    patterns1 = extract_all_patterns(
        history1, output_path=pattern_path1, state_logs_by_session=state_logs1
    )

    v1 = sum(1 for c in pass1_claims if c["status"] == "VALIDATED")
    p1 = sum(1 for c in pass1_claims if c["status"] == "PARTIAL")
    i1 = sum(1 for c in pass1_claims if c["status"] == "INVALIDATED")
    print(f"\nPass 1: {len(pass1_claims)} claims  V={v1} P={p1} I={i1}")
    print(f"Numeric error: {patterns1.get('numeric_error_distribution')}")
    print(f"State bias: {patterns1.get('state_prediction_bias')}")
    print(f"Recommendation: {patterns1.get('state_threshold_recommendation')}")

    # PASS 2: calibrated
    print("\n" + "=" * 60)
    print("PASS 2: CALIBRATED FROM PASS 1 PATTERNS")
    print("=" * 60)
    pass2_dir = os.path.join(workspace, "pass2")
    pass2_claims = []
    pass2_dirs = []
    for i in range(8):
        decider = EnvAwareDecider(
            pattern_table_path=pattern_path1,
            db_adapter=adapter,
        )
        sdir = os.path.join(pass2_dir, f"session_{i:03d}")
        sid = f"pass2_{i}"
        session = Session(
            scenario_name="environment_modulated_drift",
            ai_decide=decider,
            output_dir=sdir,
            seed=i,
            max_ticks=200,
            db_adapter=adapter,
        )
        session.run()
        for c in _read_claims(os.path.join(sdir, "CLAIM_TABLE.substrate.json")):
            c["_scenario_name"] = "environment_modulated_drift"
            c["_session_id"] = sid
            pass2_claims.append(c)
        pass2_dirs.append((sid, sdir))

    history2 = os.path.join(workspace, "pass2_history.json")
    with open(history2, "w") as f:
        json.dump(pass2_claims, f, indent=2)
    state_logs2 = load_state_logs(pass2_dirs)
    pattern_path2 = os.path.join(workspace, "pass2_PATTERN_TABLE.json")
    patterns2 = extract_all_patterns(
        history2, output_path=pattern_path2, state_logs_by_session=state_logs2
    )

    v2 = sum(1 for c in pass2_claims if c["status"] == "VALIDATED")
    p2 = sum(1 for c in pass2_claims if c["status"] == "PARTIAL")
    i2 = sum(1 for c in pass2_claims if c["status"] == "INVALIDATED")
    print(f"\nPass 2: {len(pass2_claims)} claims  V={v2} P={p2} I={i2}")
    print(f"Numeric error: {patterns2.get('numeric_error_distribution')}")
    print(f"State bias: {patterns2.get('state_prediction_bias')}")

    # Compare
    print("\n" + "=" * 60)
    print("DELTA")
    print("=" * 60)
    n1 = patterns1.get("numeric_error_distribution")
    n2 = patterns2.get("numeric_error_distribution")
    if n1 and n2:
        print(f"  Mean abs error: {n1['mean']:.2f} → {n2['mean']:.2f}")
    sb1 = patterns1.get("state_prediction_bias")
    sb2 = patterns2.get("state_prediction_bias")
    if sb1 and sb2:
        print(f"  State accuracy: {sb1.get('overall_state_accuracy', 0):.2f} → "
              f"{sb2.get('overall_state_accuracy', 0):.2f}")
    print(f"  Validated:      {v1} → {v2}")
    print(f"  Partial:        {p1} → {p2}")
    print(f"  Invalidated:    {i1} → {i2}")


if __name__ == "__main__":
    run_two_pass()
