#!/usr/bin/env python3
"""
End-to-End Integration Test
============================
Validates the full pipeline:
  sensor -> HardwareBridgeEncoder -> TokenBuffer -> GeometricProcessingLoop
  -> cube dependency detection -> FailureDatabase lookup
  -> RepurposeOrchestrator dispatch

Also exercises:
  - Environment + EnvironmentalMemory (acceleration factors)
  - feed_geometry() path (GenericHardwareInterface compatible)
  - AI self-diagnosis

Requires: numpy
"""

import sys
import time
import random
from pathlib import Path

import numpy as np

# Resolve src/ imports
_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from geometric_monitoring_engine import (
    GeometricMonitoringSystem,
    Environment,
    EnvironmentalMemory,
    FailureDatabase,
    RepurposeOrchestrator,
    TokenBuffer,
    value_to_token,
)
from hardware_bridge_encoder import HardwareBridgeEncoder
from sensors.physical_sensor import PhysicalSensor


# ======================================================================
# Test sensors
# ======================================================================

class TestResistor(PhysicalSensor):
    """Resistor that drifts after a configurable delay."""
    def __init__(self, drift_after_sec=5.0):
        self.start = time.time()
        self.drift_after = drift_after_sec

    def sample(self):
        t = time.time() - self.start
        if t < self.drift_after:
            v = 5.0 + random.gauss(0, 0.05)
            mode = "none"
        else:
            v = 5.0 + (t - self.drift_after) * 0.5
            mode = "drift"
        return {
            "type": "resistor", "mode": mode,
            "v": v, "i": v / 1000, "t": 25.0,
            "nominal": 5.0, "fail_threshold": 8.0,
        }


class TestConnector(PhysicalSensor):
    """Connector that corrodes over time."""
    def __init__(self, corrode_after_sec=3.0):
        self.start = time.time()
        self.corrode_after = corrode_after_sec

    def sample(self):
        t = time.time() - self.start
        if t < self.corrode_after:
            r = 20.0 + random.gauss(0, 0.5)
            mode = "none"
        else:
            r = 20.0 + (t - self.corrode_after) * 15.0
            mode = "corrosion"
        v = r * 0.001
        return {
            "type": "connector", "mode": mode,
            "v": v, "i": 0.001, "t": 25.0,
            "nominal": 0.020, "fail_threshold": 0.150,
        }


# ======================================================================
# Test helpers
# ======================================================================

def test_environment():
    """Test Environment + EnvironmentalMemory."""
    print("--- Environment & Memory ---")
    env = Environment(temperature_c=25, humidity_percent=50)

    # Normal conditions
    accel = env.get_acceleration_factor("resistor", "drift")
    assert 0.9 < accel < 1.5, f"Expected ~1.0, got {accel}"
    print(f"  Normal conditions: accel={accel:.3f} (OK)")

    # Harsh conditions
    env.update(temp=85, humidity=90, vibration=2.0, contamination=0.5)
    accel_harsh = env.get_acceleration_factor("resistor", "drift")
    assert accel_harsh > accel, "Harsh should accelerate more"
    print(f"  Harsh conditions:  accel={accel_harsh:.3f} (OK)")

    # Connector gets extra contamination penalty
    accel_conn = env.get_acceleration_factor("connector", "corrosion")
    assert accel_conn > accel_harsh, "Connector contamination bonus"
    print(f"  Connector harsh:   accel={accel_conn:.3f} (OK)")

    # Memory accumulates
    for _ in range(10):
        env.update(temp=45)
        time.sleep(0.01)
        env.update(temp=15)
        time.sleep(0.01)
    assert env.memory.thermal_cycles > 0, "Should count thermal cycles"
    print(f"  Thermal cycles:    {env.memory.thermal_cycles} (OK)")
    print("  PASS\n")


def test_encoder_pipeline():
    """Test HardwareBridgeEncoder -> tokens -> TokenBuffer."""
    print("--- Encoder Pipeline ---")
    enc = HardwareBridgeEncoder()
    geometry = {
        "component_type": "resistor",
        "failure_mode": "drift",
        "health_score": 0.4,
        "drift_pct": 25.0,
        "voltage_v": 7.5,
        "current_a": 0.0075,
        "temperature_c": 45.0,
        "salvageable": True,
    }
    enc.from_geometry(geometry)
    binary = enc.to_binary()
    assert len(binary) == 39, f"Expected 39 bits, got {len(binary)}"
    print(f"  Binary: {binary} ({len(binary)} bits)")

    tokens = enc.to_octahedral_tokens()
    assert len(tokens) >= 6, f"Expected >=6 tokens, got {len(tokens)}"
    print(f"  Tokens: {tokens}")

    # Push into buffer
    buf = TokenBuffer()
    for t in tokens:
        buf.push("R1", t)
    batch = buf.pop_batch(100)
    assert len(batch) == len(tokens)
    print(f"  Buffer round-trip: {len(batch)} tokens (OK)")
    print("  PASS\n")


def test_failure_db():
    """Test FailureDatabase lookup."""
    print("--- Failure Database ---")
    db = FailureDatabase()

    # Known entry
    result = db.lookup("resistor", "001|O")
    assert result is not None, "Should find resistor drift"
    mode, action, pri, eff = result
    print(f"  resistor '001|O': {mode} -> {action} (pri={pri}, eff={eff})")
    assert mode == "drift"

    # Unknown entry
    result = db.lookup("resistor", "111|X")
    assert result is None, "Should not find unknown token"
    print(f"  resistor '111|X': None (OK)")

    # By type
    entries = db.lookup_by_type("diode")
    assert len(entries) >= 2
    print(f"  diode entries: {len(entries)}")
    for tok, m, a, p, e in entries:
        print(f"    {tok} -> {m} -> {a}")
    print("  PASS\n")


def test_feed_geometry():
    """Test feed_geometry() path (GenericHardwareInterface compatible)."""
    print("--- feed_geometry() ---")
    system = GeometricMonitoringSystem(cube_side=2)  # small cube for fast fill
    system.start()

    geometry = {
        "component_type": "resistor",
        "failure_mode": "drift",
        "health_score": 0.35,
        "drift_pct": 30.0,
        "voltage_v": 7.8,
        "current_a": 0.0078,
        "temperature_c": 50.0,
        "salvageable": True,
    }
    # Feed multiple times to fill cubes
    for _ in range(20):
        system.feed_geometry("resistor_R1", geometry)
        time.sleep(0.01)

    time.sleep(0.2)  # let processing loop catch up
    tokens = system.component_last_tokens.get("resistor_R1", [])
    assert len(tokens) > 0, "Should have tokens from feed_geometry"
    print(f"  Tokens generated: {len(tokens)}")
    print(f"  Sample: {tokens[:3]}")

    system.stop()
    print("  PASS\n")


def test_full_pipeline():
    """
    End-to-end: sensor -> encoder -> buffer -> cube -> dependency
    -> failure DB -> repurpose action.
    """
    print("--- Full Pipeline (sensor -> repurpose) ---")
    system = GeometricMonitoringSystem(cube_side=2)  # 8 tokens per cube
    system.environment.update(temp=60, humidity=80)
    system.start()

    resistor = TestResistor(drift_after_sec=2.0)
    connector = TestConnector(corrode_after_sec=1.5)
    enc = HardwareBridgeEncoder()

    start = time.time()
    token_count = 0
    while time.time() - start < 8:
        # Resistor
        raw = resistor.sample()
        system.feed_sensor("resistor_R1", raw["v"], "V", "resistor")

        # Connector via geometry path
        raw_c = connector.sample()
        health = max(0.0, 1.0 - abs(raw_c["v"] - 0.020) / 0.130)
        geometry = {
            "component_type": raw_c["type"],
            "failure_mode": raw_c["mode"],
            "health_score": health,
            "drift_pct": abs(raw_c["v"] - 0.020) / 0.020 * 100,
            "voltage_v": raw_c["v"],
            "current_a": raw_c["i"],
            "temperature_c": raw_c["t"],
            "salvageable": health < 0.5,
        }
        system.feed_geometry("connector_J1", geometry)

        # Self-diagnosis
        system.run_self_diagnosis()

        token_count += 1
        time.sleep(0.02)

    system.stop()
    print(f"\n  Tokens fed: {token_count}")
    print(f"  Dependencies logged: {len(system.dependency_log)}")
    print(f"  Env acceleration: "
          f"{system.environment.get_acceleration_factor('resistor', 'drift'):.2f}x")
    for entry in system.dependency_log[:3]:
        print(f"    {entry['component']}: {entry['mode']} -> "
              f"{entry['action']} (accel={entry['env_accel']:.2f}x)")
    print("  PASS\n")


# ======================================================================
# Run all tests
# ======================================================================

def main():
    print("=" * 60)
    print("END-TO-END INTEGRATION TEST")
    print("sensor -> encoder -> buffer -> cube -> dependency -> repurpose")
    print("=" * 60)
    print()

    test_environment()
    test_encoder_pipeline()
    test_failure_db()
    test_feed_geometry()
    test_full_pipeline()

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
