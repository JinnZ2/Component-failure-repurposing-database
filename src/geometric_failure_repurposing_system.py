#!/usr/bin/env python3
"""
Geometric Failure Repurposing System
====================================
Integrates:
- HardwareBridgeEncoder (39‑bit → octahedral tokens)
- GenericHardwareInterface (sensor sampling, health/drift)
- TokenBuffer & GeometricProcessingLoop (3D cube cancellation)
- FailureDatabase (lookup failure → repurpose action)
- RepurposeOrchestrator (prioritised fallback channels)
- GeometricMonitoringSystem (main orchestrator)

Run with: python geometric_failure_repurposing_system.py
"""

import time
import threading
import hashlib
import random
import math
from abc import ABC, abstractmethod
from collections import deque
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass

# Try to import numpy for efficient cube operations; fallback to pure Python
try:
    import numpy as np
    USE_NUMPY = True
except ImportError:
    USE_NUMPY = False
    print("NumPy not available. Using pure Python fallback (slower).")

# =============================================================================
# 1. Hardware Bridge Encoder (39‑bit to octahedral tokens)
# =============================================================================
class HardwareBridgeEncoder:
    """Maps physical parameters to 39‑bit binary and octahedral tokens."""
    def __init__(self):
        self.bits = 39
        self.binary_str = "0" * self.bits

    def from_geometry(self, geometry: dict) -> 'HardwareBridgeEncoder':
        """Encode geometry dict into a 39‑bit binary string."""
        data_str = (
            f"{geometry.get('component_type','')}"
            f"{geometry.get('failure_mode','')}"
            f"{geometry.get('health_score',0):.3f}"
            f"{geometry.get('drift_pct',0):.3f}"
            f"{geometry.get('voltage_v',0):.3f}"
            f"{geometry.get('current_a',0):.3f}"
            f"{geometry.get('temperature_c',25):.3f}"
            f"{geometry.get('salvageable',False)}"
        )
        h = hashlib.sha256(data_str.encode()).digest()
        value = int.from_bytes(h, 'big') & ((1 << self.bits) - 1)
        self.binary_str = f"{value:0{self.bits}b}"
        return self

    def to_binary(self) -> str:
        return self.binary_str

    def to_octahedral_tokens(self) -> List[str]:
        """Chunk 39‑bit binary into 6‑bit octahedral tokens."""
        full = self.binary_str
        if len(full) % 6 != 0:
            full = full.ljust((len(full) + 5) // 6 * 6, '0')
        tokens = []
        sym_map = {'00':'O','01':'I','10':'X','11':'Δ'}
        for i in range(0, len(full), 6):
            chunk = full[i:i+6]
            vertex = chunk[:3]
            op_bit = chunk[3]
            sym_bits = chunk[4:6]
            operator = '|' if op_bit == '1' else '/'
            symbol = sym_map.get(sym_bits, 'O')
            tokens.append(f"{vertex}{operator}{symbol}")
        return tokens

# =============================================================================
# 2. Physical Sensor Abstraction
# =============================================================================
class PhysicalSensor(ABC):
    @abstractmethod
    def sample(self) -> dict:
        """Return a dict with keys: type, mode, v, i, t, nominal, fail_threshold, ..."""
        pass

class SimulatedResistor(PhysicalSensor):
    """Simulates a resistor that drifts after 10 seconds."""
    def __init__(self, nominal_voltage=5.0, fail_voltage=8.0, drift_start=10.0):
        self.nominal = nominal_voltage
        self.fail = fail_voltage
        self.drift_start = drift_start
        self.start_time = time.time()

    def sample(self) -> dict:
        elapsed = time.time() - self.start_time
        if elapsed < self.drift_start:
            v = self.nominal + random.uniform(-0.1, 0.1)
            mode = "none"
        else:
            # Drift upward
            drift_factor = min(1.0, (elapsed - self.drift_start) / 10.0)
            v = self.nominal + drift_factor * (self.fail - self.nominal)
            v += random.uniform(-0.2, 0.2)
            mode = "drift"
        health = max(0.0, 1.0 - abs(v - self.nominal) / abs(self.fail - self.nominal))
        drift_pct = abs(v - self.nominal) / abs(self.nominal) * 100 if self.nominal != 0 else 0
        return {
            "type": "resistor",
            "mode": mode,
            "health_score": health,
            "drift_pct": drift_pct,
            "v": v,
            "i": v / 1000.0,   # assume 1k load
            "t": 25.0,
            "salvageable": health < 0.5,
            "nominal": self.nominal,
            "fail_threshold": self.fail
        }

# =============================================================================
# 3. Generic Hardware Interface (Low‑Entropy Gateway)
# =============================================================================
class GenericHardwareInterface:
    """Maps physical sensors to the 39‑bit encoder and feeds geometric monitor."""
    def __init__(self, encoder: HardwareBridgeEncoder, geo_monitor=None):
        self.encoder = encoder
        self.geo_monitor = geo_monitor  # GeometricMonitoringSystem instance
        self.sensors: Dict[str, PhysicalSensor] = {}
        self.history: List[dict] = []   # for drift tracking

    def register_sensor(self, name: str, sensor: PhysicalSensor):
        self.sensors[name] = sensor

    def get_system_state(self) -> Dict[str, dict]:
        """Sample all sensors, compute health/drift, feed to geometric monitor, return report."""
        report = {}
        for name, sensor in self.sensors.items():
            raw = sensor.sample()
            health = self._calculate_health(raw)
            drift = self._calculate_drift(raw)
            geometry = {
                "component_type": raw.get("type", "default"),
                "failure_mode": raw.get("mode", "none"),
                "health_score": health,
                "drift_pct": drift,
                "voltage_v": raw.get("v", 0.0),
                "current_a": raw.get("i", 0.0),
                "temperature_c": raw.get("t", 25.0),
                "salvageable": health < 0.5
            }
            # Feed to geometric monitoring if available
            if self.geo_monitor:
                self.geo_monitor.feed_geometry(name, geometry)
            # Encode to binary
            binary = self.encoder.from_geometry(geometry).to_binary()
            report[name] = {
                "binary": binary,
                "hex": hex(int(binary, 2)),
                "status": "OPERATIONAL" if health > 0.7 else "REPURPOSE_TARGET"
            }
            # Store history for drift analysis
            self.history.append({"name": name, "health": health, "time": time.time()})
            if len(self.history) > 1000:
                self.history.pop(0)
        return report

    def _calculate_health(self, data: dict) -> float:
        """H = max(0, 1 - |x - x₀| / |x_fail - x₀|)"""
        x0 = data.get("nominal", 5.0)
        x_fail = data.get("fail_threshold", 8.0)
        x = data.get("v", x0)
        if x_fail == x0:
            return 1.0
        return max(0.0, 1.0 - abs(x - x0) / abs(x_fail - x0))

    def _calculate_drift(self, data: dict) -> float:
        """D = |x - x₀| / |x₀| * 100"""
        x0 = data.get("nominal", 5.0)
        x = data.get("v", x0)
        if x0 == 0:
            return 0.0
        return abs(x - x0) / abs(x0) * 100.0

# =============================================================================
# 4. Token Buffer (Lock‑free ring buffer)
# =============================================================================
class TokenBuffer:
    def __init__(self, capacity: int = 10000):
        self.buffer = deque(maxlen=capacity)
        self.lock = threading.Lock()
        self.dropped = 0

    def push(self, component_id: str, token: str, priority: int = 0) -> bool:
        with self.lock:
            if len(self.buffer) >= self.buffer.maxlen:
                self.dropped += 1
                return False
            self.buffer.append((component_id, token, priority, time.time()))
            return True

    def pop_batch(self, max_count: int = 100) -> List[tuple]:
        with self.lock:
            batch = []
            for _ in range(min(max_count, len(self.buffer))):
                batch.append(self.buffer.popleft())
            return batch

    def size(self) -> int:
        with self.lock:
            return len(self.buffer)

# =============================================================================
# 5. Geometric Processing Loop (3D cubes & dependency detection)
# =============================================================================
def token_to_vertex(token: str) -> int:
    """Extract 3‑bit vertex (0‑7) from token."""
    return int(token[:3], 2)

def tokens_to_cube(tokens: List[str], side: int = 4):
    """Return a cube (list of lists or numpy array) of vertices."""
    total = side ** 3
    if USE_NUMPY:
        cube = np.zeros((side, side, side), dtype=np.uint8)
    else:
        cube = [[[0 for _ in range(side)] for _ in range(side)] for _ in range(side)]
    idx = 0
    for i in range(side):
        for j in range(side):
            for k in range(side):
                if idx < len(tokens):
                    val = token_to_vertex(tokens[idx])
                    if USE_NUMPY:
                        cube[i, j, k] = val
                    else:
                        cube[i][j][k] = val
                idx += 1
    return cube

def cube_equal(cube1, cube2) -> bool:
    """Compare two cubes (numpy or nested lists)."""
    if USE_NUMPY:
        return np.array_equal(cube1, cube2)
    else:
        if len(cube1) != len(cube2):
            return False
        for i in range(len(cube1)):
            for j in range(len(cube1[0])):
                for k in range(len(cube1[0][0])):
                    if cube1[i][j][k] != cube2[i][j][k]:
                        return False
        return True

class GeometricProcessingLoop:
    """Accumulates tokens into cubes, detects repeated cubes (dependencies)."""
    def __init__(self, token_buffer: TokenBuffer, cube_side: int = 4):
        self.buffer = token_buffer
        self.cube_side = cube_side
        self.cube_capacity = cube_side ** 3
        self.token_stream = deque(maxlen=self.cube_capacity)
        self.cubes_history = []   # list of cubes (numpy or nested lists)
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
            batch = self.buffer.pop_batch(max_count=50)
            for comp_id, token, prio, ts in batch:
                self.token_stream.append(token)
                if len(self.token_stream) == self.cube_capacity:
                    cube = tokens_to_cube(list(self.token_stream), self.cube_side)
                    # Check for duplicate
                    match_idx = None
                    for i, prev in enumerate(self.cubes_history):
                        if cube_equal(cube, prev):
                            match_idx = i
                            break
                    self.cubes_history.append(cube)
                    if len(self.cubes_history) > 20:
                        self.cubes_history.pop(0)
                    if match_idx is not None:
                        for cb in self.dependency_callbacks:
                            cb(match_idx, len(self.cubes_history)-1)
                    self.token_stream.clear()
            time.sleep(0.001)

# =============================================================================
# 6. Failure Database (in‑memory, can be loaded from JSON/YAML)
# =============================================================================
class FailureDatabase:
    """Maps (component_type, token) -> (failure_mode, action, priority, effectiveness)."""
    def __init__(self):
        # Built‑in demo data; replace with actual YAML/JSON loader
        self.db = {}
        # Populate with some failure modes for resistor
        self._add_entry("resistor", "001|O", "drift", "rf_beacon", priority=1, effectiveness=0.85)
        self._add_entry("resistor", "101/Δ", "open", "optical_fallback", priority=2, effectiveness=0.7)
        self._add_entry("resistor", "010||X", "short", "acoustic_alarm", priority=3, effectiveness=0.6)

    def _add_entry(self, comp, token, mode, action, priority, effectiveness):
        key = (comp, token)
        self.db[key] = (mode, action, priority, effectiveness)

    def lookup(self, component_type: str, token: str) -> Optional[Tuple[str, str, int, float]]:
        """Return (failure_mode, action, priority, effectiveness) or None."""
        return self.db.get((component_type.lower(), token))

# =============================================================================
# 7. Repurpose Orchestrator (tries fallback actions in priority order)
# =============================================================================
class RepurposeOrchestrator:
    """
    Executes fallback actions based on priority.
    In a real system, each action would interface with hardware (GPIO, etc.).
    Here we simulate with print statements.
    """
    def __init__(self):
        self.available_actions = {
            "rf_beacon": self._action_rf_beacon,
            "optical_fallback": self._action_optical,
            "acoustic_alarm": self._action_acoustic,
            "thermal_heater": self._action_thermal,
            "magnetic_coupling": self._action_magnetic,
            "mechanical_vibration": self._action_mechanical,
        }

    def execute(self, action_name: str, component_id: str, params: dict = None) -> bool:
        """Execute an action, return True if successful (ACK received)."""
        if action_name not in self.available_actions:
            print(f"  ⚠️ Unknown action '{action_name}'")
            return False
        print(f"  🔧 Executing {action_name} for {component_id}")
        success = self.available_actions[action_name](component_id, params)
        if success:
            print(f"  ✅ {action_name} succeeded")
        else:
            print(f"  ❌ {action_name} failed")
        return success

    def _action_rf_beacon(self, comp_id, params):
        print("     📡 Transmitting RF beacon (OOK): 'FAIL:' + comp_id")
        # Simulate ACK
        time.sleep(0.5)
        return True

    def _action_optical(self, comp_id, params):
        print("     💡 Blinking LED SOS pattern")
        time.sleep(0.5)
        return True

    def _action_acoustic(self, comp_id, params):
        print("     🔊 Sounding piezo buzzer (Morse 'SOS')")
        time.sleep(0.5)
        return True

    def _action_thermal(self, comp_id, params):
        print("     🔥 Activating resistor heater (thermal beacon)")
        time.sleep(0.5)
        return True

    def _action_magnetic(self, comp_id, params):
        print("     🧲 Engaging magnetic coil coupling")
        time.sleep(0.5)
        return True

    def _action_mechanical(self, comp_id, params):
        print("     📳 Vibrating motor (mechanical signalling)")
        time.sleep(0.5)
        return True

# =============================================================================
# 8. Geometric Monitoring System (Main orchestrator)
# =============================================================================
class GeometricMonitoringSystem:
    """Ties together hardware interface, token buffer, processing, DB, and repurposing."""
    def __init__(self, cube_side: int = 4):
        self.token_buffer = TokenBuffer(capacity=10000)
        self.processing = GeometricProcessingLoop(self.token_buffer, cube_side)
        self.db = FailureDatabase()
        self.orchestrator = RepurposeOrchestrator()
        self.encoder = HardwareBridgeEncoder()
        self.hardware = GenericHardwareInterface(self.encoder, geo_monitor=self)
        self.component_last_tokens = {}   # component_id -> list of tokens (optional)
        self.processing.on_dependency(self._on_dependency)
        self.running = False

    def register_sensor(self, name: str, sensor: PhysicalSensor):
        self.hardware.register_sensor(name, sensor)

    def feed_geometry(self, component_id: str, geometry: dict):
        """Called by hardware interface to push geometry into the token pipeline."""
        self.encoder.from_geometry(geometry)
        tokens = self.encoder.to_octahedral_tokens()
        self.component_last_tokens[component_id] = tokens
        for token in tokens:
            self.token_buffer.push(component_id, token)

    def _on_dependency(self, prev_idx: int, curr_idx: int):
        print(f"\n🔔 GEOMETRIC DEPENDENCY: Cube {curr_idx} repeats cube {prev_idx}")
        # For each component that contributed to the cube, look up the last token
        # In a full implementation, we would track which tokens belong to which component.
        # Here we simply take the last token of each registered component.
        for comp_id, tokens in self.component_last_tokens.items():
            if not tokens:
                continue
            # Use the first token of the component (or the most recent)
            token = tokens[0]
            # Determine component type from sensor (we can store mapping separately)
            comp_type = comp_id.split('_')[0] if '_' in comp_id else comp_id
            entry = self.db.lookup(comp_type, token)
            if entry:
                mode, action, priority, effectiveness = entry
                print(f"   → Component {comp_id} matches failure '{mode}' (eff={effectiveness}, prio={priority})")
                # Execute repurpose action
                self.orchestrator.execute(action, comp_id)
                # Optionally, only act on first matched component
                break

    def start(self):
        self.running = True
        self.processing.start()
        print("Geometric Monitoring System started.")

    def stop(self):
        self.running = False
        self.processing.stop()
        print("Geometric Monitoring System stopped.")

    def run_forever(self, sample_interval: float = 0.5):
        """Continuously sample hardware and report state."""
        try:
            while self.running:
                state = self.hardware.get_system_state()
                for comp_id, info in state.items():
                    if info['status'] == 'REPURPOSE_TARGET':
                        # Already handled via dependency, but we can also log
                        pass
                time.sleep(sample_interval)
        except KeyboardInterrupt:
            self.stop()

# =============================================================================
# 9. Main Demo
# =============================================================================
def main():
    print("=" * 70)
    print("GEOMETRIC FAILURE REPURPOSING SYSTEM")
    print("Simulating a drifting resistor → geometric cube dependency → repurpose action")
    print("=" * 70)

    # Create monitoring system
    system = GeometricMonitoringSystem(cube_side=3)   # 27 tokens per cube
    # Register a simulated resistor
    resistor = SimulatedResistor(nominal_voltage=5.0, fail_voltage=8.0, drift_start=10.0)
    system.register_sensor("resistor_R1", resistor)

    # Start system
    system.start()

    # Run the main loop (samples every 0.5 seconds, will trigger dependency after ~10-15 sec)
    print("\nMonitoring resistor... (will drift after 10 seconds)")
    print("When a cube repeats (dependency), a repurpose action (RF beacon) will be triggered.\n")
    system.run_forever(sample_interval=0.5)

if __name__ == "__main__":
    main()
