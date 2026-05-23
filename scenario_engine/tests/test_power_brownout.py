"""Focused tests for the PowerBrownout scenario."""

import unittest

from scenario_engine.scenarios import REGISTRY, PowerBrownout


class PowerBrownoutBasicsTests(unittest.TestCase):
    def test_registered(self):
        self.assertIn("power_brownout", REGISTRY)
        self.assertIs(REGISTRY["power_brownout"], PowerBrownout)

    def test_deterministic(self):
        a = PowerBrownout(seed=3, max_ticks=20)
        b = PowerBrownout(seed=3, max_ticks=20)
        sa = [a.step().to_dict() for _ in range(20)]
        sb = [b.step().to_dict() for _ in range(20)]
        self.assertEqual(sa, sb)


class RailVoltageProfileTests(unittest.TestCase):
    def test_holds_nominal_before_sag(self):
        s = PowerBrownout()
        for _ in range(5):
            st = s.step()
        # ticks 0..4 are before sag_start=10
        v = st.actual_outcome["V_3V3"]
        self.assertAlmostEqual(v, 3.30, places=2)
        self.assertEqual(st.actual_outcome["system_state"], "stable")

    def test_sags_to_minimum_after_complete(self):
        s = PowerBrownout()
        # Step past sag_complete=60
        for _ in range(70):
            st = s.step()
        v = st.actual_outcome["V_3V3"]
        # At tick 69, well past sag_complete=60, no shedding: should be at V_min
        self.assertLess(v, 3.00)

    def test_recovery_returns_voltage(self):
        s = PowerBrownout(max_ticks=200)
        # Step through full sag and into recovery (recovery_start=150, returns over 30 ticks)
        states = [s.step() for _ in range(200)]
        v_late = states[-1].actual_outcome["V_3V3"]
        # By tick 199 (>>180), rail has recovered to nominal
        self.assertAlmostEqual(v_late, 3.30, places=2)


class ComponentThresholdTests(unittest.TestCase):
    def test_u2_degrades_first_then_u1_then_u3(self):
        """U2 needs >3.10, U1 needs >3.00, U3 needs >2.90."""
        s = PowerBrownout()
        first_degraded = {"U1": None, "U2": None, "U3": None}
        for _ in range(80):
            st = s.step()
            for cid in first_degraded:
                if first_degraded[cid] is None and \
                   st.actual_outcome[f"{cid}_state"] in ("degraded", "failed"):
                    first_degraded[cid] = st.tick
        # U2 has the highest threshold → degrades first.
        self.assertIsNotNone(first_degraded["U2"])
        self.assertLess(first_degraded["U2"], first_degraded["U1"])
        self.assertLess(first_degraded["U1"], first_degraded["U3"])


class InterventionTests(unittest.TestCase):
    def test_shed_load_u2_raises_rail(self):
        baseline = PowerBrownout()
        for _ in range(60):
            base_state = baseline.step()
        v_no_shed = base_state.actual_outcome["V_3V3"]

        intervened = PowerBrownout()
        for _ in range(20):
            intervened.step()
        intervened.receive_intervention("shed_load_U2", 20)
        for _ in range(40):
            iv_state = intervened.step()
        v_shed = iv_state.actual_outcome["V_3V3"]
        # Shedding U2 should raise the rail.
        self.assertGreater(v_shed, v_no_shed)
        # U2 reports offline
        self.assertEqual(iv_state.actual_outcome["U2_state"], "offline")

    def test_switch_backup_rail_clamps_to_3v25(self):
        s = PowerBrownout()
        for _ in range(30):
            s.step()
        s.receive_intervention("switch_backup_rail", 30)
        for _ in range(10):
            st = s.step()
        self.assertAlmostEqual(st.actual_outcome["V_3V3"], 3.25, places=2)
        # System state should be stable on backup (all thresholds met by 3.25V).
        self.assertEqual(st.actual_outcome["system_state"], "stable")

    def test_ignore_intervention_does_nothing(self):
        s = PowerBrownout()
        for _ in range(20):
            s.step()
        s.receive_intervention("ignore", 20)
        for _ in range(40):
            st = s.step()
        # Nothing shed, no backup → rail is sagging
        self.assertLess(st.actual_outcome["V_3V3"], 3.30)
        self.assertEqual(set(s.shed), set())
        self.assertFalse(s.backup_active)


if __name__ == "__main__":
    unittest.main()
