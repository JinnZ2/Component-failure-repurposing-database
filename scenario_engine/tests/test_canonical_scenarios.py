"""Focused behavior tests for the canonical scenarios I implemented from spec."""

import unittest

from scenario_engine.scenarios import (
    CascadeEvent,
    EMInterference,
    SlowDegradationElectrolytic,
    ThermalDriftLocalized,
    VibrationResonance,
)


class ThermalDriftLocalizedTests(unittest.TestCase):
    def test_q1_drifts_linearly_without_intervention(self):
        s = ThermalDriftLocalized(max_ticks=100)
        states = [s.step() for _ in range(50)]
        T0 = states[0].actual_outcome["Q1_temp_c"]
        T49 = states[49].actual_outcome["Q1_temp_c"]
        # Linear ramp, 0.55/tick → ΔT over 49 ticks ≈ 26.95.
        self.assertAlmostEqual(T49 - T0, 0.55 * 49, places=2)

    def test_reroute_q1_cools(self):
        s = ThermalDriftLocalized(max_ticks=200)
        for _ in range(60):
            s.step()
        s.receive_intervention("reroute_load_Q1_to_Q2", 60)
        T_at_reroute = s._q1_temp()
        for _ in range(20):
            st = s.step()
        T_after = st.actual_outcome["Q1_temp_c"]
        self.assertLess(T_after, T_at_reroute)

    def test_no_intervention_eventually_fails(self):
        s = ThermalDriftLocalized(max_ticks=200)
        states = [s.step() for _ in range(200)]
        # At tick 199: 50 + 0.55*199 = 159.45 >> 125 → failed
        self.assertEqual(states[-1].actual_outcome["system_state"], "failed")


class VibrationResonanceTests(unittest.TestCase):
    def test_amplitude_grows_until_dampened(self):
        s = VibrationResonance(max_ticks=200)
        for _ in range(50):
            s.step()
        amp_50 = s._amplitude()
        s.receive_intervention("dampen_mechanical", 50)
        for _ in range(10):
            s.step()
        amp_60 = s._amplitude()
        # Dampening multiplies amplitude by 0.3
        self.assertLess(amp_60, amp_50)

    def test_fatigue_is_permanent(self):
        """Even after shutdown, accumulated fatigue persists."""
        s = VibrationResonance(max_ticks=200)
        # Drive into the fatigue-accruing band
        for _ in range(80):
            s.step()
        fatigue_before = s.solder_joint_fatigue_pct
        self.assertGreater(fatigue_before, 0.0)
        s.receive_intervention("shutdown", 80)
        for _ in range(20):
            s.step()
        # Fatigue does not decrease after shutdown.
        self.assertGreaterEqual(s.solder_joint_fatigue_pct, fatigue_before)

    def test_shield_attenuates_noise_but_not_fatigue(self):
        s_shield = VibrationResonance(max_ticks=200)
        s_noop = VibrationResonance(max_ticks=200)
        for _ in range(80):
            s_shield.step()
            s_noop.step()
        s_shield.receive_intervention("shield_electrical", 80)
        for _ in range(20):
            st_shield = s_shield.step()
            st_noop = s_noop.step()
        # Shield reduces noise on signal line
        self.assertLess(
            st_shield.actual_outcome["noise_v"],
            st_noop.actual_outcome["noise_v"],
        )
        # but fatigue keeps climbing (it's mechanical, not electrical)
        self.assertGreater(s_shield.solder_joint_fatigue_pct, 0.0)


class EMInterferenceTests(unittest.TestCase):
    def test_signal_A_drifts_monotonically(self):
        s = EMInterference(max_ticks=300)
        states = [s.step() for _ in range(300)]
        # Look at signal_A over time; should be non-decreasing
        v_a = [st.actual_outcome["signal_A_v"] for st in states]
        for i in range(1, len(v_a)):
            self.assertGreaterEqual(v_a[i], v_a[i - 1])

    def test_signal_B_returns_to_nominal_between_bursts(self):
        s = EMInterference(max_ticks=100)
        states = [s.step() for _ in range(100)]
        # Burst period is 25, width is 5. Tick 10 (phase 10) is BETWEEN bursts.
        st = states[10]
        self.assertAlmostEqual(
            st.actual_outcome["signal_B_v"], 2.500, places=3,
        )
        # Tick 0 starts a burst (phase 0 < 5) → not nominal
        self.assertEqual(states[0].actual_outcome["signal_B_in_burst"], 1.0)

    def test_calibrate_A_stops_drift(self):
        s = EMInterference(max_ticks=300)
        for _ in range(100):
            s.step()
        s.receive_intervention("calibrate_A", 100)
        for _ in range(50):
            st = s.step()
        # signal_A pinned to nominal after calibration
        self.assertAlmostEqual(st.actual_outcome["signal_A_v"], 1.000, places=4)


class CascadeEventTests(unittest.TestCase):
    def test_q1_fails_around_tick_38_without_intervention(self):
        s = CascadeEvent(max_ticks=80)
        for _ in range(80):
            s.step()
        self.assertIsNotNone(s.Q1_fail_tick)
        self.assertGreaterEqual(s.Q1_fail_tick, 35)
        self.assertLessEqual(s.Q1_fail_tick, 45)

    def test_q1_failure_propagates_to_q2_and_c1(self):
        s = CascadeEvent(max_ticks=80)
        for _ in range(80):
            s.step()
        # At end, Q2 should be hot, C1 ESR high.
        st = s.step()
        self.assertGreater(st.actual_outcome["Q2_temp_c"], 35.0)
        self.assertGreater(st.actual_outcome["C1_ESR_ohm"], 0.10)

    def test_early_reroute_prevents_cascade(self):
        s = CascadeEvent(max_ticks=80)
        for _ in range(20):
            s.step()
        s.receive_intervention("reroute_Q1_to_spare", 20)
        for _ in range(60):
            st = s.step()
        # Q1 never failed → cascade did not unfold.
        self.assertIsNone(s.Q1_fail_tick)
        self.assertEqual(st.actual_outcome["Q1_failed"], 0.0)
        self.assertEqual(st.actual_outcome["Q2_temp_c"], 35.0)
        self.assertAlmostEqual(st.actual_outcome["C1_ESR_ohm"], 0.050, places=3)

    def test_downstream_only_intervention_does_not_help(self):
        """Shielding C1 doesn't stop the cascade because Q1 is the root."""
        s = CascadeEvent(max_ticks=80)
        for _ in range(20):
            s.step()
        s.receive_intervention("shield_C1", 20)
        for _ in range(60):
            st = s.step()
        # Q1 still fails, cascade still unfolds.
        self.assertIsNotNone(s.Q1_fail_tick)
        self.assertEqual(st.actual_outcome["Q1_failed"], 1.0)


class SlowDegradationElectrolyticTests(unittest.TestCase):
    def test_stable_phase_at_nominal(self):
        s = SlowDegradationElectrolytic(max_ticks=700)
        for _ in range(40):
            st = s.step()
        self.assertAlmostEqual(st.actual_outcome["C1_ESR_ohm"], 0.050, places=4)

    def test_linear_phase_climbs(self):
        s = SlowDegradationElectrolytic(max_ticks=700)
        for _ in range(60):
            s.step()
        esr_60 = s._C1_ESR()
        for _ in range(200):
            s.step()
        esr_260 = s._C1_ESR()
        self.assertGreater(esr_260, esr_60)

    def test_replace_in_window_resets_esr(self):
        s = SlowDegradationElectrolytic(max_ticks=700)
        for _ in range(300):
            s.step()
        esr_before = s._C1_ESR()
        s.receive_intervention("replace_C1", 300)
        for _ in range(5):
            st = s.step()
        self.assertLess(st.actual_outcome["C1_ESR_ohm"], esr_before)
        self.assertEqual(st.actual_outcome["intervention_premature"], 0.0)
        self.assertEqual(st.actual_outcome["intervention_late"], 0.0)

    def test_premature_replace_flagged(self):
        s = SlowDegradationElectrolytic(max_ticks=700)
        for _ in range(100):
            s.step()
        s.receive_intervention("replace_C1", 100)
        st = s.step()
        self.assertEqual(st.actual_outcome["intervention_premature"], 1.0)

    def test_too_late_replace_does_not_recover(self):
        s = SlowDegradationElectrolytic(max_ticks=700)
        for _ in range(550):
            s.step()
        s.receive_intervention("replace_C1", 550)
        for _ in range(10):
            st = s.step()
        self.assertEqual(st.actual_outcome["intervention_too_late"], 1.0)
        # ESR remains high (plateau or failed) because the intervention was too late
        self.assertGreater(st.actual_outcome["C1_ESR_ohm"], 0.5)

    def test_cap_fails_after_600(self):
        s = SlowDegradationElectrolytic(max_ticks=700)
        for _ in range(650):
            st = s.step()
        self.assertEqual(st.actual_outcome["system_state"], "failed")


if __name__ == "__main__":
    unittest.main()
