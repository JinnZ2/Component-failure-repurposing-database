#!/usr/bin/env python3
"""
Geometric Failure Diagnosis (standalone version)
=================================================
Maps component failure modes to octahedral tokens, simulates degradation,
and detects repeated patterns (dependencies) via 3D cube cancellation.
Also demonstrates AI self-diagnosis via internal state cubes.

Note: An enhanced version that loads real data from the database CSVs
lives at ``experiments/sims/geometric_failure_diagnosis.py``.
"""

import hashlib
import time
import random
import numpy as np
from collections import deque
from typing import List, Tuple, Dict

# ----------------------------------------------------------------------
# Token generation from failure mode
# ----------------------------------------------------------------------
def failure_to_token(component_type: str, failure_mode: str, severity: str = "gradual") -> str:
    """
    Map component + failure mode to a deterministic geometric token.
    severity: "abrupt", "gradual", "intermittent"
    repurpose: "none", "low", "medium", "high" (derived from db)
    """
    # Vertex bits: hash of component+mode mod 8
    key = f"{component_type}:{failure_mode}"
    h = int(hashlib.md5(key.encode()).hexdigest()[:2], 16) % 8
    vertex = f"{h:03b}"
    # Operator mapping
    op_map = {"abrupt": "|", "gradual": "/", "intermittent": "||"}
    operator = op_map.get(severity, "/")
    # Symbol (repurpose potential) – for demo we derive from hash
    sym_idx = (h >> 1) % 4
    symbol = ["O", "I", "X", "Δ"][sym_idx]
    return f"{vertex}{operator}{symbol}"

# ----------------------------------------------------------------------
# Simulate a degrading component (e.g., diode)
# ----------------------------------------------------------------------
def simulate_degradation(component: str, failure_modes: List[str], duration_sec: float = 30, rate_hz: float = 2):
    """
    Yield geometric tokens over time as component degrades.
    Failure modes appear with increasing probability.
    """
    start = time.time()
    # Initial probability of each failure mode (healthy)
    probs = [0.05] * len(failure_modes)
    # Degradation curve: linear increase over time
    end = start + duration_sec
    while time.time() < end:
        elapsed = time.time() - start
        t = elapsed / duration_sec  # 0 → 1
        # Increase probability of each failure mode
        current_probs = [p + t * 0.8 for p in probs]  # max ~0.85
        # Choose a failure mode (or none)
        if random.random() < sum(current_probs):
            idx = random.choices(range(len(failure_modes)), weights=current_probs)[0]
            mode = failure_modes[idx]
            # Severity increases with time
            if t < 0.3:
                severity = "gradual"
            elif t < 0.7:
                severity = "intermittent"
            else:
                severity = "abrupt"
            token = failure_to_token(component, mode, severity)
            yield token
        # Wait for next sample
        time.sleep(1.0 / rate_hz)

# ----------------------------------------------------------------------
# 3D Cube dependency detector (same as before)
# ----------------------------------------------------------------------
def tokens_to_cube(tokens: List[str], side: int = 4) -> np.ndarray:
    cube = np.zeros((side, side, side), dtype=np.uint8)
    idx = 0
    for i in range(side):
        for j in range(side):
            for k in range(side):
                if idx < len(tokens):
                    vertex_bits = tokens[idx][:3]
                    cube[i,j,k] = int(vertex_bits, 2)
                idx += 1
    return cube

def find_repeated_cube(cubes_history: List[np.ndarray]) -> Tuple[bool, int]:
    """Check if latest cube matches any previous cube."""
    if len(cubes_history) < 2:
        return False, -1
    latest = cubes_history[-1]
    for i, prev in enumerate(cubes_history[:-1]):
        if np.array_equal(latest, prev):
            return True, i
    return False, -1

# ----------------------------------------------------------------------
# AI self-diagnosis: monitor internal state as cube
# ----------------------------------------------------------------------
def internal_state_token(metric_name: str, value: float, thresholds: Tuple[float,float]) -> str:
    """
    Map an internal metric (e.g., CPU usage, latency) to a token.
    thresholds: (low, high) for normal range.
    """
    # Determine vertex from normalized value (0-7)
    norm = min(1.0, max(0.0, (value - thresholds[0]) / (thresholds[1] - thresholds[0])))
    vertex = f"{int(norm * 7):03b}"
    # Operator: radial if value is extreme
    if value < thresholds[0] or value > thresholds[1]:
        operator = "|"
    else:
        operator = "/"
    # Symbol: based on trend (simplified: use value)
    sym_idx = int((value * 10) % 4)
    symbol = ["O", "I", "X", "Δ"][sym_idx]
    return f"{vertex}{operator}{symbol}"

def ai_self_diagnose(interval_sec: float = 5, cube_side: int = 3):
    """
    Periodically sample internal metrics (simulated), build cubes,
    and detect repeated patterns (self-diagnosis).
    """
    metrics = ["cpu_usage", "memory_usage", "response_latency", "error_rate"]
    token_buffer = deque(maxlen=cube_side**3)
    cubes_history = []
    last_time = time.time()

    print("AI Self-Diagnosis active. Watching for repeated state cubes...")
    while True:
        now = time.time()
        if now - last_time >= interval_sec:
            # Simulate metric values (in real system, read from /proc or API)
            fake_values = {
                "cpu_usage": random.uniform(10, 90),
                "memory_usage": random.uniform(20, 80),
                "response_latency": random.uniform(5, 200),
                "error_rate": random.uniform(0, 5),
            }
            for metric in metrics:
                val = fake_values[metric]
                # Define normal range per metric
                if metric == "cpu_usage":
                    thresh = (20, 70)
                elif metric == "memory_usage":
                    thresh = (30, 75)
                elif metric == "response_latency":
                    thresh = (10, 100)
                else:
                    thresh = (0, 2)
                token = internal_state_token(metric, val, thresh)
                token_buffer.append(token)
                if len(token_buffer) == cube_side**3:
                    cube = tokens_to_cube(list(token_buffer), cube_side)
                    cubes_history.append(cube)
                    repeated, idx = find_repeated_cube(cubes_history)
                    if repeated:
                        print(f"⚠️ Self-diagnosis: Cube repeated (match with cube {idx})")
                        print(f"   → System may be in a failure/recovery cycle.")
                        # Optionally, trigger corrective action
                    cubes_history = cubes_history[-10:]  # keep last 10
            last_time = now
        time.sleep(0.5)

# ----------------------------------------------------------------------
# Demo: component failure simulation + geometric diagnosis
# ----------------------------------------------------------------------
def demo():
    print("=" * 70)
    print("GEOMETRIC FAILURE DIAGNOSIS")
    print("Using octahedral tokens + 3D cube cancellation")
    print("=" * 70)

    # Example failure modes for silicon diode (from your database)
    diode_modes = [
        "short circuit",
        "open circuit",
        "increased leakage current",
        "breakdown voltage shift",
        "thermal runaway"
    ]

    print(f"\nSimulating degradation of a silicon diode over 20 seconds...")
    print(f"Failure modes: {diode_modes}")

    token_buffer = deque(maxlen=64)   # 4x4x4 cube
    cubes_history = []
    start_time = time.time()

    for token in simulate_degradation("silicon_diode", diode_modes, duration_sec=20, rate_hz=4):
        token_buffer.append(token)
        if len(token_buffer) == 64:
            cube = tokens_to_cube(list(token_buffer), side=4)
            cubes_history.append(cube)
            repeated, idx = find_repeated_cube(cubes_history)
            if repeated:
                print(f"\n🔔 DEPENDENCY DETECTED! Cube repeats pattern from cube #{idx}")
                print(f"   → The component's failure signature has become periodic.")
                print(f"   → Geometric cancellation implies a predictable failure cascade.")
            else:
                print(f"✓ New cube formed. Total cubes: {len(cubes_history)}")
            # Keep history limited
            cubes_history = cubes_history[-10:]

    print(f"\nSimulation finished. {len(cubes_history)} cubes generated.")
    print("\n" + "=" * 70)
    print("Now launching AI self-diagnosis loop (Ctrl+C to stop)...")
    try:
        ai_self_diagnose(interval_sec=3, cube_side=3)
    except KeyboardInterrupt:
        print("\nSelf-diagnosis stopped.")

if __name__ == "__main__":
    demo()
