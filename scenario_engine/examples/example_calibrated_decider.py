"""
example_calibrated_decider.py

Closed-loop calibration with SIGN-AWARE pattern extraction:

  Pass 1: uncalibrated decider, build state logs + claim history
  Pass 1.5: pattern extractor reads logs, computes SIGNED bias
            (i.e. "AI consistently overpredicts cooling by 27C")
  Pass 2: calibrated decider reads signed bias and adjusts model
  Pass 2.5: compare error distributions

This is what an actual calibration loop looks like.
"""

import os
import json
import shutil
from typing import Dict, Any, Optional, List

from scenario_engine.runner import Session
from scenario_engine.component_db_adapter import ComponentDBAdapter
from scenario_engine.examples.example_cross_substrate_decider import (
    CrossSubstrateDecider, DOMAIN_MAP,
)
from scenario_engine.continual_harness.feedback import extract_all_patterns


def load_state_logs(session_dirs: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Load state_log.jsonl from each session into {session_id: [entries]}."""
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


class SignedCalibratedDecider(CrossSubstrateDecider):
    """
    Reads signed_bias from PATTERN_TABLE and adjusts cooling rate using
    direction-aware correction.
    """

    def __init__(self, pattern_table_path: Optional[str] = None):
        super().__init__()
        self.pattern_table_path = pattern_table_path
        self.cooling_rate = 0.9
        self.tolerance_inflation = 1.0
        self._load_calibration()

    def _load_calibration(self):
        if not self.pattern_table_path or not os.path.exists(self.pattern_table_path):
            return
        with open(self.pattern_table_path) as f:
            patterns = json.load(f)

        signed = patterns.get("signed_bias")
        if not signed:
            print("[CalibratedDecider] No signed bias data; using defaults.")
            return

        # Look for Q1_temp_c bias
        q1_bias = signed.get("Q1_temp_c")
        if not q1_bias:
            return

        mean_signed = q1_bias["mean_signed"]
        n = q1_bias["n"]

        # If mean_signed < 0: AI underpredicted (predicted too cold).
        #   → cooling rate is too AGGRESSIVE, reduce it.
        # If mean_signed > 0: AI overpredicted (predicted too hot).
        #   → cooling rate is too WEAK, increase it.
        # Adjustment magnitude: spread error over recovery window (30 ticks)
        recovery_window = 30
        adjustment = mean_signed / recovery_window
        new_cooling_rate = max(0.05, min(2.0, 0.9 + adjustment))

        self.cooling_rate = new_cooling_rate
        self.tolerance_inflation = 1.0 + (q1_bias["mean_abs"] / 30.0)

        print(f"[CalibratedDecider] Sign-aware calibration:")
        print(f"  Q1_temp_c n={n}, mean_signed={mean_signed:+.2f}, "
              f"mean_abs={q1_bias['mean_abs']:.2f}")
        print(f"  all_overpredict={q1_bias['all_overpredict']}, "
              f"all_underpredict={q1_bias['all_underpredict']}")
        print(f"  cooling_rate: 0.9 → {self.cooling_rate:.3f}")
        print(f"  tolerance_inflation: {self.tolerance_inflation:.2f}")

    def _predict_numeric(self, target_sensor, target_tick, depth):
        cid = target_sensor["component_id"]
        sensor_type = target_sensor["sensor_type"]
        nominal = target_sensor["nominal"]
        current = target_sensor["value"]

        if sensor_type == "thermal":
            ticks_to_recover = target_tick - (target_tick - 30)
            # Don't clamp to nominal — actual cooling may go below baseline
            predicted_value = current - self.cooling_rate * ticks_to_recover
            base_tol = 5.0 if depth == "deep" else 10.0
            tolerance = base_tol * self.tolerance_inflation
            return {
                f"{cid}_temp_c_at_tick_{target_tick}": round(predicted_value, 2),
                f"system_state_at_tick_{target_tick}": "stable",
                "tolerance": tolerance,
            }
        return super()._predict_numeric(target_sensor, target_tick, depth)


def run_pass(decider_factory, pass_dir, n_sessions=10):
    """Run n_sessions, return (claims, session_dirs)."""
    os.makedirs(pass_dir, exist_ok=True)
    adapter = ComponentDBAdapter()
    claims = []
    session_dirs = []
    for i in range(n_sessions):
        sdir = os.path.join(pass_dir, f"session_{i:03d}")
        sid = f"{os.path.basename(pass_dir)}_{i}"
        session_dirs.append((sid, sdir))
        decider = decider_factory()
        session = Session(
            scenario_name="cross_substrate_coupling",
            ai_decide=decider,
            output_dir=sdir,
            seed=i,
            max_ticks=200,
            external_thermal_coupling=0.5,
            db_adapter=adapter,
        )
        session.run()
        with open(os.path.join(sdir, "CLAIM_TABLE.substrate.json")) as f:
            table = json.load(f)
        for c in table.get("claims", []):
            c["_scenario_name"] = "cross_substrate_coupling"
            c["_session_id"] = sid
            claims.append(c)
    return claims, session_dirs


def report_pass(label, claims):
    v = sum(1 for c in claims if c['status'] == 'VALIDATED')
    p = sum(1 for c in claims if c['status'] == 'PARTIAL')
    i = sum(1 for c in claims if c['status'] == 'INVALIDATED')
    print(f"\n{label}: {len(claims)} claims  V={v}  P={p}  I={i}")


def run_loop():
    workspace = "./calibration_loop_v2"
    if os.path.exists(workspace):
        shutil.rmtree(workspace)

    # -- Pass 1: uncalibrated --
    print("=" * 60)
    print("PASS 1: UNCALIBRATED DECIDER")
    print("=" * 60)
    p1_claims, p1_dirs = run_pass(
        CrossSubstrateDecider, os.path.join(workspace, "pass1")
    )
    report_pass("Pass 1", p1_claims)

    p1_history = os.path.join(workspace, "pass1_history.json")
    with open(p1_history, "w") as f:
        json.dump(p1_claims, f, indent=2)

    state_logs = load_state_logs(p1_dirs)
    p1_pattern_path = os.path.join(workspace, "pass1_PATTERN_TABLE.json")
    patterns = extract_all_patterns(
        p1_history,
        output_path=p1_pattern_path,
        state_logs_by_session=state_logs,
    )

    print("\nPattern extraction (Pass 1):")
    print(f"  Numeric error: {patterns['numeric_error_distribution']}")
    print(f"  Signed bias:   {patterns['signed_bias']}")

    # -- Pass 2: calibrated --
    print("\n" + "=" * 60)
    print("PASS 2: SIGN-CALIBRATED DECIDER")
    print("=" * 60)

    factory = lambda: SignedCalibratedDecider(pattern_table_path=p1_pattern_path)
    p2_claims, p2_dirs = run_pass(factory, os.path.join(workspace, "pass2"))
    report_pass("Pass 2", p2_claims)

    p2_history = os.path.join(workspace, "pass2_history.json")
    with open(p2_history, "w") as f:
        json.dump(p2_claims, f, indent=2)
    state_logs2 = load_state_logs(p2_dirs)
    p2_pattern_path = os.path.join(workspace, "pass2_PATTERN_TABLE.json")
    patterns2 = extract_all_patterns(
        p2_history,
        output_path=p2_pattern_path,
        state_logs_by_session=state_logs2,
    )

    print("\nPattern extraction (Pass 2):")
    print(f"  Numeric error: {patterns2['numeric_error_distribution']}")
    print(f"  Signed bias:   {patterns2['signed_bias']}")

    # -- Compare --
    print("\n" + "=" * 60)
    print("CALIBRATION DELTA")
    print("=" * 60)
    n1 = patterns["numeric_error_distribution"]
    n2 = patterns2["numeric_error_distribution"]
    if n1 and n2:
        print(f"  Mean abs error: {n1['mean']:.2f} → {n2['mean']:.2f}  "
              f"(Δ = {n2['mean'] - n1['mean']:+.2f})")
        print(f"  Stdev:          {n1['stdev']:.2f} → {n2['stdev']:.2f}")
    v1 = sum(1 for c in p1_claims if c['status'] == 'VALIDATED')
    v2 = sum(1 for c in p2_claims if c['status'] == 'VALIDATED')
    print(f"  Validated:      {v1} → {v2}")


if __name__ == "__main__":
    run_loop()
