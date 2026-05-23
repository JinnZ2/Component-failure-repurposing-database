"""Behavior tests for the environment_modulated_drift scenario."""

import unittest

from scenario_engine.scenarios import EnvironmentModulatedDrift


class NominalPhaseTests(unittest.TestCase):
    def test_nominal_drift_rate_under_25C(self):
        """During the nominal phase (ticks 0-30), rate ≈ base_drift = 0.3 C/tick."""
        s = EnvironmentModulatedDrift()
        for _ in range(20):
            st = s.step()
        # Phase nominal: ambient_factor = 1, humidity_factor = 1 → rate = 0.3
        self.assertAlmostEqual(st.actual_outcome["env_temp_c"], 25.0)
        # Q1_T = 65 + 0.3 * (19 - 5 + 1) = 65 + 4.5 = 69.5
        self.assertAlmostEqual(st.actual_outcome["Q1_temp_c"], 69.5, places=2)


class HarshPhaseTests(unittest.TestCase):
    def test_harsh_phase_accelerates_drift(self):
        s = EnvironmentModulatedDrift()
        for _ in range(40):  # past tick 30 into harsh phase
            st = s.step()
        # At tick 39: env_temp = 45, humidity = 85
        self.assertAlmostEqual(st.actual_outcome["env_temp_c"], 45.0)
        # ambient_factor = 2^((45-25)/10) = 4
        # humidity_factor = 1 + (85-70)/30 = 1.5
        # harsh rate = 0.3 * 4 * 1.5 = 1.8 C/tick
        # Q1_T = 65 + 25*0.3 + 10*1.8 = 65 + 7.5 + 18 = 90.5
        self.assertAlmostEqual(st.actual_outcome["Q1_temp_c"], 90.5, places=2)


class FailureTimingTests(unittest.TestCase):
    def test_fails_during_harsh_phase_without_intervention(self):
        s = EnvironmentModulatedDrift(max_ticks=200)
        for _ in range(80):  # full harsh phase
            st = s.step()
        # Should have hit the 130C limit during harsh phase
        self.assertGreaterEqual(st.actual_outcome["Q1_temp_c"], 130.0)
        self.assertEqual(st.actual_outcome["system_state"], "failed")

    def test_reroute_intervention_cools(self):
        s = EnvironmentModulatedDrift(max_ticks=200)
        for _ in range(15):
            s.step()
        s.receive_intervention("reroute_load_to_spare", 15)
        for _ in range(20):
            st = s.step()
        # After 20 ticks of -0.5 rate, T should drop
        # Without intervention at tick 34 (still nominal phase pre-30)
        # Q1_T would be 65 + 0.3*30 = 74. With reroute starting tick 15:
        # T at tick 14 = 65 + 0.3*10 = 68; then -0.5*20 over ticks 15-34 = -10
        # Final ≈ 58
        self.assertLess(st.actual_outcome["Q1_temp_c"], 70.0)


class EnvMemoryTests(unittest.TestCase):
    def test_cycling_phase_does_not_cross_20C_threshold(self):
        """
        Documents a spec gap: the cycling phase alternates 25°C ↔ 55°C,
        which never crosses the 20°C threshold that EnvironmentalMemory
        defines as a thermal cycle. The scenario's docstring says
        'cumulative damage builds' during cycling but the implementation
        doesn't actually generate cycle counts. Future refinement:
        either lower the cool side to below 20°C, or change the
        memory's threshold to detect peak-to-peak swings.
        """
        s = EnvironmentModulatedDrift(max_ticks=200)
        for _ in range(160):
            st = s.step()
        # Today: 0 thermal cycles register (gap).
        self.assertEqual(st.actual_outcome["thermal_cycles"], 0)

    def test_humidity_exposure_accumulates_in_harsh_phase(self):
        s = EnvironmentModulatedDrift(max_ticks=100)
        for _ in range(80):  # full harsh phase at 85% RH
            st = s.step()
        # Harsh phase = 50 ticks at 85% RH, dt=1.0 each → 50s exposure
        self.assertGreaterEqual(st.actual_outcome["humidity_exposure_seconds"], 40.0)


if __name__ == "__main__":
    unittest.main()
