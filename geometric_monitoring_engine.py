#!/usr/bin/env python3
"""
Geometric Monitoring Engine
---------------------------
Replaces binary sensor processing with octahedral tokens and 3D cube cancellation.
Integrates component failure database and AI self-diagnosis.
"""

import time
import threading
import hashlib
import sys
from pathlib import Path
import numpy as np
from collections import deque
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass

# Import canonical GEIS classes from experiments/sims
_SIMS = Path(__file__).resolve().parent / "experiments" / "sims"
if str(_SIMS) not in sys.path:
    sys.path.insert(0, str(_SIMS))

from geometric_sensing_sim import (  # noqa: E402
    OctahedralState,
    GeometricEncoder,
    StateTensor,
)

def value_to_token(reading: float, units: str, component_type: str) -> str:
    """
    Convert a raw sensor reading to an octahedral token.
    Uses reading magnitude to select vertex, rate of change for operator,
    and component type to derive symbol.
    """
    # Vertex: quantize reading into 0..7
    norm = min(1.0, abs(reading) / 10.0)  # assume 0-10V or similar
    vertex = f"{int(norm * 7):03b}"
    # Operator: radial if reading is extreme (out of safe range)
    safe_range = (0.5, 5.0)  # example
    if reading < safe_range[0] or reading > safe_range[1]:
        operator = "|"
    else:
        operator = "/"
    # Symbol: derived from component type hash
    h = hashlib.md5(component_type.encode()).hexdigest()
    sym_idx = int(h[0], 16) % 4
    symbol = ["O","I","X","Δ"][sym_idx]
    return f"{vertex}{operator}{symbol}"

def token_to_vertex(token: str) -> int:
    return int(token[:3], 2)

# ----------------------------------------------------------------------
# 2. Input Buffer Queue (adapted from original)
# ----------------------------------------------------------------------
class TokenBuffer:
    def __init__(self, capacity=10000):
        self.buffer = deque(maxlen=capacity)
        self.lock = threading.Lock()
        self.dropped = 0

    def push(self, component_id: str, token: str, priority=0):
        with self.lock:
            if len(self.buffer) >= self.buffer.maxlen:
                self.dropped += 1
                return False
            self.buffer.append((component_id, token, priority, time.time()))
            return True

    def pop_batch(self, max_count=100):
        with self.lock:
            batch = []
            for _ in range(min(max_count, len(self.buffer))):
                batch.append(self.buffer.popleft())
            return batch

# ----------------------------------------------------------------------
# 3. 3D Cube & Dependency Detection
# ----------------------------------------------------------------------
def tokens_to_cube(tokens: List[str], side=4) -> np.ndarray:
    cube = np.zeros((side,side,side), dtype=np.uint8)
    idx = 0
    for i in range(side):
        for j in range(side):
            for k in range(side):
                if idx < len(tokens):
                    cube[i,j,k] = token_to_vertex(tokens[idx])
                idx += 1
    return cube

def cube_hash(cube: np.ndarray) -> bytes:
    """Hash of cube (optionally rotate‑invariant)."""
    # Simple: flatten bytes
    return cube.tobytes()

def find_repeated_cube(cubes_history: List[np.ndarray]) -> Optional[Tuple[int,int]]:
    """Returns (index_of_match, current_index) if current cube repeats."""
    if len(cubes_history) < 2:
        return None
    current = cubes_history[-1]
    for i, prev in enumerate(cubes_history[:-1]):
        if np.array_equal(current, prev):
            return (i, len(cubes_history)-1)
    return None

# ----------------------------------------------------------------------
# 4. Failure Database Lookup (simulated)
# ----------------------------------------------------------------------
FAILURE_DB = {
    "diode": {"short": "000|O", "open": "001|I", "leakage": "010|X"},
    "resistor": {"drift": "100/Δ", "open": "101/|"},
}

def lookup_failure(component_type: str, token: str) -> Optional[str]:
    """Return failure mode if token matches a known failure pattern."""
    for mode, tok in FAILURE_DB.get(component_type, {}).items():
        if tok == token:
            return mode
    return None

# ----------------------------------------------------------------------
# 5. Geometric Processing Loop (replaces CoreProcessingLoop)
# ----------------------------------------------------------------------
class GeometricProcessingLoop:
    def __init__(self, token_buffer: TokenBuffer, cube_side=4):
        self.token_buffer = token_buffer
        self.cube_side = cube_side
        self.cube_capacity = cube_side**3
        self.token_stream = deque(maxlen=self.cube_capacity)
        self.cubes_history = []   # list of np.ndarray
        self.running = False
        self.thread = None
        self.dependency_callbacks = []

    def on_dependency(self, callback: Callable[[int, int], None]):
        self.dependency_callbacks.append(callback)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def _loop(self):
        while self.running:
            batch = self.token_buffer.pop_batch(max_count=50)
            for comp_id, token, prio, ts in batch:
                self.token_stream.append(token)
                if len(self.token_stream) == self.cube_capacity:
                    cube = tokens_to_cube(list(self.token_stream), self.cube_side)
                    self.cubes_history.append(cube)
                    # Keep last 20 cubes
                    if len(self.cubes_history) > 20:
                        self.cubes_history.pop(0)
                    # Check for repeat
                    match = find_repeated_cube(self.cubes_history)
                    if match:
                        for cb in self.dependency_callbacks:
                            cb(match[0], match[1])
                    # Clear stream for next cube
                    self.token_stream.clear()
            time.sleep(0.001)  # prevent busy loop

# ----------------------------------------------------------------------
# 6. AI Self‑Diagnosis Plugin
# ----------------------------------------------------------------------
class AISelfDiagnosis:
    """Monitors internal AI metrics (CPU, memory, latency) via cubes."""
    def __init__(self, interval_sec=5, cube_side=3):
        self.interval = interval_sec
        self.cube_side = cube_side
        self.token_stream = deque(maxlen=cube_side**3)
        self.history = []
        self.last_check = time.time()

    def step(self) -> Optional[Tuple[int,int]]:
        now = time.time()
        if now - self.last_check < self.interval:
            return None
        self.last_check = now
        # Simulate internal metrics
        metrics = {
            "cpu": np.random.uniform(10,90),
            "mem": np.random.uniform(20,80),
            "latency": np.random.uniform(5,200),
        }
        for name, val in metrics.items():
            # Convert metric to token
            norm = min(1.0, val/100.0)
            vertex = f"{int(norm*7):03b}"
            operator = "|" if val > 80 else "/"
            sym_idx = int(val) % 4
            symbol = ["O","I","X","Δ"][sym_idx]
            token = f"{vertex}{operator}{symbol}"
            self.token_stream.append(token)
            if len(self.token_stream) == self.cube_side**3:
                cube = tokens_to_cube(list(self.token_stream), self.cube_side)
                self.history.append(cube)
                if len(self.history) > 10:
                    self.history.pop(0)
                match = find_repeated_cube(self.history)
                if match:
                    return match
                self.token_stream.clear()
        return None

# ----------------------------------------------------------------------
# 7. Complete Monitoring System (integrated)
# ----------------------------------------------------------------------
class GeometricMonitoringSystem:
    def __init__(self, cube_side=4):
        self.token_buffer = TokenBuffer()
        self.processing = GeometricProcessingLoop(self.token_buffer, cube_side)
        self.ai_diag = AISelfDiagnosis(interval_sec=3, cube_side=3)
        self.processing.on_dependency(self._on_dependency)

    def _on_dependency(self, prev_idx, curr_idx):
        print(f"🔔 GEOMETRIC DEPENDENCY: Cube {curr_idx} repeats cube {prev_idx}")
        print("   → Possible component failure or system cycle detected.")

    def feed_sensor(self, component_id: str, value: float, units: str, comp_type: str):
        token = value_to_token(value, units, comp_type)
        self.token_buffer.push(component_id, token)

    def start(self):
        self.processing.start()
        print("Geometric Monitoring Engine started.")

    def stop(self):
        self.processing.stop()

    def run_self_diagnosis(self):
        result = self.ai_diag.step()
        if result:
            print(f"⚠️ AI SELF-DIAGNOSIS: Internal state cube repeated (match {result})")
        return result

# ----------------------------------------------------------------------
# 8. Demo: Simulate sensor feed and self-diagnosis
# ----------------------------------------------------------------------
if __name__ == "__main__":
    system = GeometricMonitoringSystem(cube_side=3)   # 27 tokens per cube
    system.start()

    # Simulate a degrading resistor over 30 seconds
    start = time.time()
    while time.time() - start < 30:
        # Normal readings (healthy)
        v = np.random.normal(5.0, 0.1)
        system.feed_sensor("R1", v, "V", "resistor")
        # Occasionally inject a failure pattern
        if np.random.random() < 0.05:
            # Drift to 8V (out of range)
            system.feed_sensor("R1", 8.5, "V", "resistor")
        # Also run AI self-diagnosis every few seconds
        system.run_self_diagnosis()
        time.sleep(0.05)

    system.stop()
    print("Demo finished.")
