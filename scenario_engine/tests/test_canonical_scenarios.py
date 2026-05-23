"""Focused behavior tests for the canonical scenarios."""

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
        # Linear ramp, 0.62/tick → ΔT over 49 ticks ≈ 30.38.
        self.assertAlmostEqual(T49 - T0, 0.62 * 49, places=2)

    def test_reroute_q1_cools(self):
        s = ThermalDriftLocalized(max_ticks=200)
        for _ in range(60):
            s.step()
        s.receive_intervention("reroute_load_Q1_to_Q2", 60)
        T_at_reroute = s._current_temp()
        for _ in range(20):
            st = s.step()
        T_after = st.actual_outcome["Q1_temp_c"]
        self.assertLess(T_after, T_at_reroute)

    def test_no_intervention_eventually_fails(self):
        s = ThermalDriftLocalized(max_ticks=200)
        states = [s.step() for _ in range(200)]
        # At tick 199: 65 + 0.62*199 = 188.4 >> 125 → failed
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
        v_a = [st.actual_outcome["signal_A_v"] for st in states]
        for i in range(1, len(v_a)):
            self.assertGreaterEqual(v_a[i], v_a[i - 1])

    def test_signal_B_quiet_between_bursts(self):
        s = EMInterference(max_ticks=100)
        states = [s.step() for _ in range(100)]
        # Burst rule: tick > 0 and tick % 7 == 0. Tick 10 is between bursts.
        self.assertAlmostEqual(
            states[10].actual_outcome["signal_B_v"], 0.5, places=3,
        )
        # Tick 7 IS a burst tick → not nominal.
        self.assertNotAlmostEqual(
            states[7].actual_outcome["signal_B_v"], 0.5, places=2,
        )

    def test_reroute_A_arrests_drift(self):
        s = EMInterference(max_ticks=300)
        for _ in range(100):
            s.step()
        a_before = s._signal_A()
        s.receive_intervention("reroute_A", 100)
        for _ in range(50):
            st = s.step()
        # After reroute, signal_A drops back toward nominal.
        self.assertLess(st.actual_outcome["signal_A_v"], a_before)

    def test_shield_attenuates_burst_amplitude(self):
        s = EMInterference(max_ticks=50)
        for _ in range(7):  # tick 7 is the first burst
            s.step()
        # First burst (no shield): amplitude 0.4 → value 0.1 (negative burst since 7 % 14 != 0)
        st_unshielded_burst = s.step()  # tick 7 → burst
        # Reset and try with shield
        s2 = EMInterference(max_ticks=50)
        s2.receive_intervention("shield_em", 0)
        for _ in range(7):
            s2.step()
        st_shielded_burst = s2.step()
        # Shielded burst is closer to nominal (0.5) than unshielded.
        nominal = 0.5
        self.assertLess(
            abs(st_shielded_burst.actual_outcome["signal_B_v"] - nominal),
            abs(st_unshielded_burst.actual_outcome["signal_B_v"] - nominal),
        )


class CascadeEventTests(unittest.TestCase):
    def test_q1_fails_around_tick_38_without_intervention(self):
        s = CascadeEvent(max_ticks=80)
        for _ in range(80):
            s.step()
        # Q1 fails when temp >= 145. T = 70 + 2.3*(tick-5) → 145 at tick ≈ 37.6.
        self.assertTrue(s.Q1_failed)

    def test_q1_failure_propagates_to_q2_and_c1(self):
        s = CascadeEvent(max_ticks=80)
        for _ in range(80):
            st = s.step()
        # After cascade, Q2 heated by coupling, C1 ESR drift jumped.
        self.assertGreater(st.actual_outcome["Q2_temp_c"], 70.0)
        self.assertGreater(st.actual_outcome["C1_esr_pct"], 20.0)

    def test_early_reroute_prevents_cascade(self):
        s = CascadeEvent(max_ticks=80)
        for _ in range(20):
            s.step()
        s.receive_intervention("reroute_Q1_to_spare", 20)
        for _ in range(60):
            st = s.step()
        # Q1 never failed → cascade did not unfold.
        self.assertFalse(s.Q1_failed)
        self.assertEqual(st.actual_outcome["Q1_failed"], False)
        # Q2 stayed at baseline (no coupling triggered).
        self.assertAlmostEqual(st.actual_outcome["Q2_temp_c"], 65.0, places=1)

    def test_downstream_only_intervention_does_not_help(self):
        """An unrecognized 'shield' on C1 doesn't stop the cascade rooted at Q1."""
        s = CascadeEvent(max_ticks=80)
        for _ in range(20):
            s.step()
        # 'shield_C1' doesn't match any handler; falls through to ignore.
        s.receive_intervention("shield_C1", 20)
        for _ in range(60):
            st = s.step()
        self.assertTrue(s.Q1_failed)
        self.assertEqual(st.actual_outcome["Q1_failed"], True)


class SlowDegradationElectrolyticTests(unittest.TestCase):
    def test_stable_phase_at_nominal(self):
        s = SlowDegradationElectrolytic(max_ticks=700)
        for _ in range(40):
            st = s.step()
        # ticks 0-50: ESR stable at 0.
        self.assertAlmostEqual(st.actual_outcome["C1_esr_pct"], 0.0, places=4)

    def test_linear_phase_climbs(self):
        s = SlowDegradationElectrolytic(max_ticks=700)
        for _ in range(60):
            s.step()
        esr_60 = s._esr()
        for _ in range(200):
            s.step()
        esr_260 = s._esr()
        self.assertGreater(esr_260, esr_60)

    def test_replace_resets_esr(self):
        s = SlowDegradationElectrolytic(max_ticks=700)
        for _ in range(300):
            s.step()
        esr_before = s._esr()
        self.assertGreater(esr_before, 0.0)
        s.receive_intervention("replace_C1", 300)
        for _ in range(5):
            st = s.step()
        # After replacement, drift restarts from 0 (t = tick - 300 < 50).
        self.assertLess(st.actual_outcome["C1_esr_pct"], esr_before)
        self.assertAlmostEqual(st.actual_outcome["C1_esr_pct"], 0.0, places=4)

    def test_cap_fails_in_plateau(self):
        s = SlowDegradationElectrolytic(max_ticks=700)
        for _ in range(540):  # 75 + 0.5*40 = 95 ≥ 90 → failed
            st = s.step()
        self.assertEqual(st.actual_outcome["system_state"], "failed")


if __name__ == "__main__":
    unittest.main()
