"""Tests for scenario_engine.environment."""

import unittest

from scenario_engine.environment import EnvironmentState, EnvironmentalMemory


class InstantaneousFactorTests(unittest.TestCase):
    def test_nominal_conditions_factor_one(self):
        env = EnvironmentState(temp_c=25.0, humidity_pct=50.0,
                               vibration_g=0.0, contamination=0.0)
        self.assertAlmostEqual(env.acceleration_factor(), 1.0, places=6)

    def test_arrhenius_10C_doubles(self):
        # 35°C = 25 + 10 → factor 2x
        env = EnvironmentState(temp_c=35.0, humidity_pct=50.0,
                               vibration_g=0.0, contamination=0.0)
        # No humidity / vibration / contamination contribution
        self.assertAlmostEqual(env.acceleration_factor(), 2.0, places=4)

    def test_arrhenius_below_25C_below_one(self):
        env = EnvironmentState(temp_c=15.0, humidity_pct=50.0,
                               vibration_g=0.0, contamination=0.0)
        # 15°C: 2 ** -1 = 0.5
        self.assertAlmostEqual(env.acceleration_factor(), 0.5, places=4)

    def test_humidity_above_70_amplifies(self):
        env = EnvironmentState(temp_c=25.0, humidity_pct=100.0,
                               vibration_g=0.0, contamination=0.0)
        # (100 - 70) / 30 = 1.0 → factor 1.0 * (1 + 1.0) = 2.0
        self.assertAlmostEqual(env.acceleration_factor(), 2.0, places=4)

    def test_humidity_70_or_below_no_effect(self):
        env = EnvironmentState(temp_c=25.0, humidity_pct=70.0,
                               vibration_g=0.0, contamination=0.0)
        self.assertAlmostEqual(env.acceleration_factor(), 1.0, places=4)

    def test_vibration_linear(self):
        env = EnvironmentState(temp_c=25.0, humidity_pct=50.0,
                               vibration_g=2.0, contamination=0.0)
        # 1 + 2.0 * 0.5 = 2.0
        self.assertAlmostEqual(env.acceleration_factor(), 2.0, places=4)

    def test_connectors_more_sensitive_to_contamination(self):
        env = EnvironmentState(temp_c=25.0, humidity_pct=50.0,
                               vibration_g=0.0, contamination=0.5)
        # connector: 1 + 0.5 * 5.0 = 3.5
        # generic:   1 + 0.5 * 2.0 = 2.0
        connector_factor = env.acceleration_factor("connector_J1")
        generic_factor = env.acceleration_factor("BJT_NPN")
        self.assertAlmostEqual(connector_factor, 3.5, places=4)
        self.assertAlmostEqual(generic_factor, 2.0, places=4)
        self.assertGreater(connector_factor, generic_factor)


class MemoryTests(unittest.TestCase):
    def test_thermal_cycle_detected_on_crossing_20C(self):
        # memory.update sees the PRIOR env state, so the first env.update
        # only seeds last_temp_c; cycles register on subsequent crossings.
        env = EnvironmentState(temp_c=15.0)
        env.update(temp_c=25.0, dt=1.0)   # seeds last_temp_c=15
        self.assertEqual(env.memory.thermal_cycles, 0)
        env.update(temp_c=10.0, dt=1.0)   # prior=25, now reading 25 crossed from 15 → cycle
        self.assertEqual(env.memory.thermal_cycles, 1)
        env.update(temp_c=30.0, dt=1.0)   # prior=10 vs 25 → another cycle
        self.assertEqual(env.memory.thermal_cycles, 2)

    def test_no_cycle_when_staying_on_one_side(self):
        env = EnvironmentState(temp_c=30.0)
        env.update(temp_c=40.0, dt=1.0)
        env.update(temp_c=50.0, dt=1.0)
        env.update(temp_c=25.0, dt=1.0)  # still above 20
        self.assertEqual(env.memory.thermal_cycles, 0)

    def test_humidity_exposure_only_above_70(self):
        env = EnvironmentState(temp_c=25.0, humidity_pct=80.0)
        env.update(dt=10.0)  # 10s at 80% RH (memory updates BEFORE applying)
        self.assertAlmostEqual(env.memory.humidity_exposure_seconds, 10.0)
        # Drop to 50% — no more accumulation
        env.update(humidity_pct=50.0, dt=5.0)
        # Still 10s recorded (memory was updated with the prior 80% state)
        self.assertAlmostEqual(env.memory.humidity_exposure_seconds, 15.0)
        # Future updates at 50% don't add
        env.update(dt=100.0)
        self.assertAlmostEqual(env.memory.humidity_exposure_seconds, 15.0)

    def test_vibration_dose_is_g_squared_dt(self):
        env = EnvironmentState(vibration_g=3.0)
        env.update(dt=2.0)
        # 3² * 2 = 18
        self.assertAlmostEqual(env.memory.vibration_dose, 18.0)
        env.update(dt=1.0)
        # +9 more
        self.assertAlmostEqual(env.memory.vibration_dose, 27.0)

    def test_contamination_deposit_saturates_at_1(self):
        env = EnvironmentState(contamination=1.0)
        # contamination=1.0, dt=10000 → deposit += 100 saturates to 1.0
        env.update(dt=10000.0)
        self.assertEqual(env.memory.contamination_deposit, 1.0)

    def test_memory_persists_after_recovery(self):
        """The whole point: damage doesn't heal."""
        env = EnvironmentState(temp_c=25.0, humidity_pct=80.0, vibration_g=2.0)
        env.update(dt=100.0)
        cycles_before = env.memory.thermal_cycles
        dose_before = env.memory.vibration_dose
        hum_before = env.memory.humidity_exposure_seconds

        # Recover to nominal
        env.update(temp_c=25.0, humidity_pct=50.0, vibration_g=0.0, dt=1.0)

        # Counters still accumulated from the stress period.
        self.assertEqual(env.memory.thermal_cycles, cycles_before)
        self.assertGreaterEqual(env.memory.vibration_dose, dose_before)
        self.assertGreaterEqual(env.memory.humidity_exposure_seconds, hum_before)


class CumulativeFactorTests(unittest.TestCase):
    def test_thermal_cycles_amplify_factor(self):
        env = EnvironmentState(vibration_g=0.0)  # isolate cumulative effect
        base = env.acceleration_factor()
        env.memory.thermal_cycles = 50
        stressed = env.acceleration_factor()
        # 50 cycles → 1 + 50*0.02 = 2.0
        self.assertAlmostEqual(stressed / base, 2.0, places=4)

    def test_humidity_hours_amplify_factor(self):
        env = EnvironmentState(vibration_g=0.0)
        env.memory.humidity_exposure_seconds = 3600.0  # 1 hour
        # 1.0 * (1 + 1*0.05) = 1.05
        self.assertAlmostEqual(env.acceleration_factor(), 1.05, places=4)

    def test_contamination_deposit_doubles_factor(self):
        env = EnvironmentState(vibration_g=0.0)
        env.memory.contamination_deposit = 1.0
        # 1 + 1 = 2.0 cumulative multiplier
        self.assertAlmostEqual(env.acceleration_factor(), 2.0, places=4)

    def test_combined_stress(self):
        env = EnvironmentState(temp_c=35.0, humidity_pct=100.0, vibration_g=0.0)
        env.memory.thermal_cycles = 100
        # Instantaneous: 2.0 (temp) * 2.0 (humidity) = 4.0
        # Cumulative: 1 + 100*0.02 = 3.0
        # Total: 12.0
        self.assertAlmostEqual(env.acceleration_factor(), 12.0, places=2)


class SerializationTests(unittest.TestCase):
    def test_to_dict_includes_memory(self):
        env = EnvironmentState(temp_c=30.0)
        env.update(temp_c=40.0, dt=1.0)
        d = env.to_dict()
        self.assertEqual(d["temp_c"], 40.0)
        self.assertIn("memory", d)
        self.assertIn("thermal_cycles", d["memory"])
        self.assertIn("acceleration_at_25C_nominal", d)

    def test_memory_to_dict(self):
        m = EnvironmentalMemory(thermal_cycles=3, vibration_dose=12.5)
        d = m.to_dict()
        self.assertEqual(d["thermal_cycles"], 3)
        self.assertEqual(d["vibration_dose"], 12.5)


if __name__ == "__main__":
    unittest.main()
