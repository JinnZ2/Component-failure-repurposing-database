"""Tests for scenario_engine.environment.synergy_validity."""

import unittest

from scenario_engine.environment import (
    EnvironmentState,
    EnvironmentalMemory,
    evaluate_synergy,
)


class LCTankGateTests(unittest.TestCase):
    def test_nominal_passes(self):
        env = EnvironmentState(temp_c=25.0)
        result = evaluate_synergy(env, "C drift + L drift", "lc_tank_rf_beacon")
        self.assertTrue(result["viable"])
        self.assertIn("lc_tank", result["gate_matched"])

    def test_above_85C_fails(self):
        env = EnvironmentState(temp_c=90.0)
        result = evaluate_synergy(env, "C drift + L drift", "lc_tank_rf_beacon")
        self.assertFalse(result["viable"])
        self.assertIn("electrolytic dryout", result["reason"])

    def test_thermal_cycles_above_50_warns(self):
        env = EnvironmentState(temp_c=25.0)
        env.memory.thermal_cycles = 60
        result = evaluate_synergy(env, "C drift + L drift", "lc_tank_rf_beacon")
        self.assertTrue(result["viable"])
        self.assertTrue(len(result["warnings"]) > 0)


class OpticalGateTests(unittest.TestCase):
    def test_high_humidity_fails(self):
        env = EnvironmentState(humidity_pct=95.0)
        result = evaluate_synergy(env, "Vf drift", "optical_fallback_sensor")
        self.assertFalse(result["viable"])
        self.assertIn("condensation", result["reason"])

    def test_heavy_contamination_fails(self):
        env = EnvironmentState(contamination=0.9)
        result = evaluate_synergy(env, "Vf drift", "optical_fallback_sensor")
        self.assertFalse(result["viable"])
        self.assertIn("contamination", result["reason"])

    def test_nominal_passes(self):
        env = EnvironmentState()
        result = evaluate_synergy(env, "Vf drift", "optical_fallback_sensor")
        self.assertTrue(result["viable"])


class ThermalArrayGateTests(unittest.TestCase):
    def test_thermal_cycles_above_20_fail(self):
        env = EnvironmentState()
        env.memory.thermal_cycles = 25
        result = evaluate_synergy(env, "Vbe + ESR", "thermal_sensing_array")
        self.assertFalse(result["viable"])
        self.assertIn("thermal cycling", result["reason"])

    def test_vibration_above_1_5_fails(self):
        env = EnvironmentState(vibration_g=2.0)
        result = evaluate_synergy(env, "Vbe + ESR", "thermal_sensing_array")
        self.assertFalse(result["viable"])
        self.assertIn("vibration", result["reason"])


class MechanicalGateTests(unittest.TestCase):
    def test_excessive_vibration_fails(self):
        env = EnvironmentState(vibration_g=5.0)
        result = evaluate_synergy(env, "strain", "mechanical_vibration_sensor")
        self.assertFalse(result["viable"])
        self.assertIn("mechanical limits", result["reason"])

    def test_high_vibration_dose_warns(self):
        env = EnvironmentState(vibration_g=1.0)
        env.memory.vibration_dose = 200.0
        result = evaluate_synergy(env, "strain", "mechanical_vibration_sensor")
        self.assertTrue(result["viable"])
        self.assertTrue(len(result["warnings"]) > 0)


class NoMatchTests(unittest.TestCase):
    def test_no_gate_keyword_returns_viable(self):
        env = EnvironmentState(temp_c=90.0)  # would fail LC gate
        # But this text has no keywords:
        result = evaluate_synergy(env, "no relevant terms", "no match")
        self.assertTrue(result["viable"])
        self.assertIsNone(result["gate_matched"])
        self.assertEqual(result["reason"], "no env gates apply")


class AccelerationFactorIncludedTests(unittest.TestCase):
    def test_accel_factor_returned(self):
        env = EnvironmentState(temp_c=35.0, vibration_g=0.0)
        result = evaluate_synergy(env, "lc_tank", "rf")
        self.assertIn("acceleration_factor", result)
        self.assertAlmostEqual(result["acceleration_factor"], 2.0, places=4)


if __name__ == "__main__":
    unittest.main()
