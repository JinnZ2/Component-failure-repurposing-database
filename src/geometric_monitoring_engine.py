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
_SIMS = Path(__file__).resolve().parent.parent / "experiments" / "sims"
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
# ----------------------------------------------------------------------
# 7. Environment + Environmental Memory
# ----------------------------------------------------------------------

class EnvironmentalMemory:
    """Tracks cumulative damage that does not heal when environment recovers."""

    def __init__(self):
        self.thermal_cycles = 0
        self.humidity_exposure_time = 0.0   # seconds above 70% RH
        self.vibration_dose = 0.0           # integral of g^2 * dt
        self.contamination_deposit = 0.0    # 0-1, accumulates
        self._last_temp = None

    def update(self, env: 'Environment', dt: float):
        # Thermal cycle: crossing 20 deg C threshold
        if self._last_temp is not None:
            if (self._last_temp - 20) * (env.temp - 20) < 0:
                self.thermal_cycles += 1
        self._last_temp = env.temp
        # Humidity exposure above 70% RH
        if env.humidity > 70:
            self.humidity_exposure_time += dt
        # Vibration dose: integral of g^2
        self.vibration_dose += env.vibration ** 2 * dt
        # Contamination deposit: accumulates, saturates at 1.0
        self.contamination_deposit = min(
            1.0, self.contamination_deposit + env.contamination * dt)


class Environment:
    """Tracks environmental conditions that affect failure rates."""

    def __init__(self, temperature_c=25.0, humidity_percent=50.0,
                 vibration_g=0.1, contamination=0.0):
        self.temp = temperature_c
        self.humidity = humidity_percent
        self.vibration = vibration_g
        self.contamination = contamination
        self.memory = EnvironmentalMemory()
        self.last_update = time.time()

    def update(self, temp=None, humidity=None, vibration=None,
               contamination=None):
        now = time.time()
        dt = now - self.last_update
        self.memory.update(self, dt)
        if temp is not None:
            self.temp = temp
        if humidity is not None:
            self.humidity = humidity
        if vibration is not None:
            self.vibration = vibration
        if contamination is not None:
            self.contamination = contamination
        self.last_update = now

    def get_acceleration_factor(self, component_type: str,
                                failure_mode: str) -> float:
        """
        Multiplier for failure progression rate.
        Combines instantaneous stress and cumulative memory damage.
        """
        # Instantaneous factors
        inst = 1.0
        inst *= 2 ** ((self.temp - 25) / 10)  # Arrhenius
        if self.humidity > 70:
            inst *= 1 + (self.humidity - 70) / 30
        inst *= 1 + self.vibration * 0.5
        if component_type == "connector":
            inst *= 1 + self.contamination * 5
        else:
            inst *= 1 + self.contamination * 2
        # Cumulative memory factors
        cum = 1.0
        cum *= 1 + self.memory.thermal_cycles * 0.02
        cum *= 1 + (self.memory.humidity_exposure_time / 3600) * 0.05
        cum *= 1 + self.memory.vibration_dose * 0.001
        cum *= 1 + self.memory.contamination_deposit
        return inst * cum


# ----------------------------------------------------------------------
# 8. Failure Database (token -> action lookup)
# ----------------------------------------------------------------------

class FailureDatabase:
    """Maps (component_type, token) -> (failure_mode, action, priority, effectiveness)."""

    def __init__(self):
        self.db: Dict[Tuple[str, str], Tuple[str, str, int, float]] = {}
        # Resistor failures
        self._add("resistor", "001|O", "drift", "rf_beacon", 1, 0.85)
        self._add("resistor", "101/\u0394", "open", "optical_fallback", 2, 0.7)
        self._add("resistor", "010||X", "short", "acoustic_alarm", 3, 0.6)
        # Diode failures
        self._add("diode", "011/I", "short", "thermal_heater", 1, 0.8)
        self._add("diode", "111/X", "open", "mechanical_vibration", 2, 0.5)
        self._add("diode", "101/I", "leakage", "rf_beacon", 2, 0.7)
        # Connector failures
        self._add("connector", "110/I", "corrosion", "magnetic_coupling", 1, 0.7)
        # Relay failures
        self._add("relay", "000|O", "contact_welding", "rf_beacon", 2, 0.8)
        self._add("relay", "111/\u0394", "coil_failure", "magnetic_coupling", 3, 0.6)
        # Motor failures
        self._add("motor", "100|O", "winding_short", "thermal_heater", 2, 0.75)
        self._add("motor", "110|X", "bearing_wear", "mechanical_vibration", 1, 0.9)

    def _add(self, comp, token, mode, action, priority, effectiveness):
        self.db[(comp.lower(), token)] = (mode, action, priority, effectiveness)

    def lookup(self, component_type: str,
               token: str) -> Optional[Tuple[str, str, int, float]]:
        return self.db.get((component_type.lower(), token))

    def lookup_by_type(self, component_type: str
                       ) -> List[Tuple[str, str, str, int, float]]:
        """All entries for a component type: [(token, mode, action, pri, eff)]."""
        results = []
        ct = component_type.lower()
        for (comp, tok), (mode, action, pri, eff) in self.db.items():
            if comp == ct:
                results.append((tok, mode, action, pri, eff))
        results.sort(key=lambda x: x[3])  # sort by priority
        return results


# ----------------------------------------------------------------------
# 9. Repurpose Orchestrator
# ----------------------------------------------------------------------

class RepurposeOrchestrator:
    """Executes fallback actions by priority."""

    ACTIONS = {
        "rf_beacon", "optical_fallback", "acoustic_alarm",
        "thermal_heater", "magnetic_coupling", "mechanical_vibration",
    }

    def execute(self, action: str, component_id: str,
                params: Optional[dict] = None) -> bool:
        if action not in self.ACTIONS:
            print(f"      Unknown action '{action}'")
            return False
        # Glyph-tagged output
        glyphs = {
            "rf_beacon": "\U0001f4e1", "optical_fallback": "\U0001f4a1",
            "acoustic_alarm": "\U0001f50a", "thermal_heater": "\U0001f525",
            "magnetic_coupling": "\U0001f9f2", "mechanical_vibration": "\U0001f4f3",
        }
        g = glyphs.get(action, "")
        print(f"  {g} Executing {action} for {component_id}")
        return True


# ----------------------------------------------------------------------
# 10. Complete Geometric Monitoring System (fully wired)
# ----------------------------------------------------------------------

class GeometricMonitoringSystem:
    """
    Main orchestrator. Wires together:
      sensors -> HardwareBridgeEncoder -> TokenBuffer -> GeometricProcessingLoop
      -> FailureDatabase lookup -> RepurposeOrchestrator dispatch
      + Environment awareness + AI self-diagnosis
    """

    def __init__(self, cube_side=4):
        self.token_buffer = TokenBuffer()
        self.processing = GeometricProcessingLoop(self.token_buffer, cube_side)
        self.ai_diag = AISelfDiagnosis(interval_sec=3, cube_side=3)
        self.failure_db = FailureDatabase()
        self.orchestrator = RepurposeOrchestrator()
        self.encoder = GeometricEncoder()
        self.environment = Environment()
        self.component_last_tokens: Dict[str, List[str]] = {}
        self.dependency_log: List[dict] = []
        self.processing.on_dependency(self._on_dependency)

    def _on_dependency(self, prev_idx, curr_idx):
        """Callback when cube repeats — look up failure and dispatch repurpose."""
        print(f"\n  DEPENDENCY: Cube {curr_idx} repeats cube {prev_idx}")
        # Check all recent component tokens against the failure database
        for comp_id, tokens in self.component_last_tokens.items():
            for token in tokens[-5:]:  # check last 5 tokens
                comp_type = comp_id.split("_")[0].lower()
                result = self.failure_db.lookup(comp_type, token)
                if result:
                    mode, action, priority, effectiveness = result
                    print(f"    {comp_id}: {mode} (eff={effectiveness:.0%}) "
                          f"-> {action}")
                    self.orchestrator.execute(action, comp_id)
                    accel = self.environment.get_acceleration_factor(
                        comp_type, mode)
                    self.dependency_log.append({
                        "time": time.time(),
                        "component": comp_id,
                        "mode": mode,
                        "action": action,
                        "env_accel": accel,
                    })
                    break  # one action per component per dependency

    def feed_sensor(self, component_id: str, value: float,
                    units: str, comp_type: str):
        """Feed a raw scalar reading into the token pipeline."""
        token = value_to_token(value, units, comp_type)
        self.token_buffer.push(component_id, token)
        self.component_last_tokens.setdefault(component_id, []).append(token)
        # Keep bounded
        if len(self.component_last_tokens[component_id]) > 100:
            self.component_last_tokens[component_id] = \
                self.component_last_tokens[component_id][-50:]

    def feed_geometry(self, component_id: str, geometry: dict):
        """
        Accept a geometry dict from GenericHardwareInterface.
        Encode to binary via HardwareBridgeEncoder, convert to
        octahedral tokens, push each into the token buffer.
        """
        from hardware_bridge_encoder import HardwareBridgeEncoder
        enc = HardwareBridgeEncoder()
        enc.from_geometry(geometry)
        tokens = enc.to_octahedral_tokens()
        self.component_last_tokens[component_id] = tokens
        for token in tokens:
            self.token_buffer.push(component_id, token)

    def start(self):
        self.processing.start()
        print("Geometric Monitoring Engine started.")

    def stop(self):
        self.processing.stop()

    def run_self_diagnosis(self) -> Optional[Tuple[int, int]]:
        result = self.ai_diag.step()
        if result:
            print(f"  AI SELF-DIAGNOSIS: Internal state cube repeated "
                  f"(match {result})")
        return result


# ----------------------------------------------------------------------
# 11. Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import random as _rng

    system = GeometricMonitoringSystem(cube_side=3)
    system.start()

    # Set up a harsh environment
    system.environment.update(temp=55, humidity=75, vibration=0.5)
    print(f"Environment: {system.environment.temp} deg C, "
          f"{system.environment.humidity}% RH, "
          f"{system.environment.vibration} g")
    accel = system.environment.get_acceleration_factor("resistor", "drift")
    print(f"Acceleration factor for resistor drift: {accel:.2f}x")

    # Show failure database entries
    print(f"\nFailure DB entries for resistor:")
    for tok, mode, action, pri, eff in system.failure_db.lookup_by_type("resistor"):
        binary = system.encoder.encode_to_binary(tok)
        print(f"  {tok} (binary={binary}) -> {mode} -> {action} "
              f"(pri={pri}, eff={eff:.0%})")

    # Simulate degrading resistor for 15 seconds
    print(f"\nSimulating degrading resistor for 15 seconds...")
    start = time.time()
    while time.time() - start < 15:
        v = _rng.gauss(5.0, 0.1)
        system.feed_sensor("resistor_R1", v, "V", "resistor")
        if _rng.random() < 0.08:
            system.feed_sensor("resistor_R1", 8.5, "V", "resistor")
        system.run_self_diagnosis()
        time.sleep(0.02)

    system.stop()
    print(f"\nDependency log: {len(system.dependency_log)} events")
    for entry in system.dependency_log[:5]:
        print(f"  {entry['component']}: {entry['mode']} -> "
              f"{entry['action']} (accel={entry['env_accel']:.2f}x)")
    print("Demo finished.")
