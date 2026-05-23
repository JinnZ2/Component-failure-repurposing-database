"""Tests for the synergy detector and the multi_failure_synergy_required scenario."""

import os
import tempfile
import unittest

from scenario_engine.component_db_adapter import ComponentDB
from scenario_engine.scenarios import MultiFailureSynergyRequired
from scenario_engine.synergy import (
    DegradedComponent,
    SynergyProposal,
    detect_synergies,
    rank_synergies_by_need,
)
from scenario_engine.synergy.synergy_detector import _confidence_from_severity


def _write_synergy_csv(d: str, rows: list):
    """Write a minimal component_synergies.csv into d/."""
    path = os.path.join(d, "component_synergies.csv")
    with open(path, "w") as f:
        f.write("Component A,Component B,Synergy Effect,Repurpose Application,Notes\n")
        for r in rows:
            f.write(",".join(r) + "\n")
    # Need the other matrices too or load_all_matrices returns []
    for name in (
        "failure_mode_matrix",
        "repurpose_effectiveness",
        "environmental_interactions",
    ):
        with open(os.path.join(d, f"{name}.csv"), "w") as f:
            f.write("Component\nx\n")


class ConfidenceTests(unittest.TestCase):
    def test_mid_severity_scores_highest(self):
        # 0.5 is the sweet spot
        self.assertAlmostEqual(_confidence_from_severity([0.5]), 1.0, places=4)
        # 0.0 (nominal) and 1.0 (failed) score lowest
        self.assertAlmostEqual(_confidence_from_severity([0.0]), 0.0, places=4)
        self.assertAlmostEqual(_confidence_from_severity([1.0]), 0.0, places=4)

    def test_averages_across_components(self):
        c = _confidence_from_severity([0.5, 0.5])
        self.assertAlmostEqual(c, 1.0, places=4)

    def test_empty_list_returns_zero(self):
        self.assertEqual(_confidence_from_severity([]), 0.0)


class DetectSynergiesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        _write_synergy_csv(self.tmp.name, [
            ["BJT_NPN", "electrolytic_cap", "Vbe + ESR", "thermal_array", "pair"],
            ["silicon_diode", "resistor", "Vf + R drift", "optical_sensor", "pair"],
        ])
        self.db = ComponentDB(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_returns_empty_for_single_component(self):
        proposals = detect_synergies(
            [DegradedComponent("Q1", "BJT_NPN", "thermal_runaway", severity=0.5)],
            self.db,
        )
        self.assertEqual(proposals, [])

    def test_matches_csv_row_to_degraded_pair(self):
        degraded = [
            DegradedComponent("Q1", "BJT_NPN", "thermal_runaway", severity=0.5),
            DegradedComponent("C1", "electrolytic_cap", "ESR_drift", severity=0.5),
        ]
        proposals = detect_synergies(degraded, self.db)
        self.assertEqual(len(proposals), 1)
        p = proposals[0]
        self.assertEqual(sorted(p.members), ["C1", "Q1"])
        self.assertEqual(p.synergy_effect, "Vbe + ESR")
        self.assertEqual(p.proposed_function, "thermal_array")
        self.assertAlmostEqual(p.confidence, 1.0, places=4)

    def test_no_match_no_proposals(self):
        degraded = [
            DegradedComponent("X1", "unrelated_type_1", "wear", severity=0.5),
            DegradedComponent("X2", "unrelated_type_2", "wear", severity=0.5),
        ]
        self.assertEqual(detect_synergies(degraded, self.db), [])

    def test_proposals_sorted_by_confidence(self):
        degraded = [
            # Q1+C1 at mid severity → high confidence
            DegradedComponent("Q1", "BJT_NPN", "thermal_runaway", severity=0.5),
            DegradedComponent("C1", "electrolytic_cap", "ESR_drift", severity=0.5),
            # D1+R1 at near-nominal → low confidence
            DegradedComponent("D1", "silicon_diode", "open", severity=0.05),
            DegradedComponent("R1", "resistor", "drift", severity=0.05),
        ]
        proposals = detect_synergies(degraded, self.db)
        self.assertEqual(len(proposals), 2)
        self.assertGreater(proposals[0].confidence, proposals[1].confidence)

    def test_pair_deduplication(self):
        # Adding the same CSV row twice via two matching A-candidates and
        # B-candidates produces only one proposal per (A,B) pair.
        degraded = [
            DegradedComponent("Q1", "BJT_NPN", "thermal_runaway", severity=0.5),
            DegradedComponent("Q2", "BJT_NPN", "thermal_runaway", severity=0.5),
            DegradedComponent("C1", "electrolytic_cap", "ESR_drift", severity=0.5),
        ]
        proposals = detect_synergies(degraded, self.db)
        # Two BJT_NPN + one electrolytic_cap → two unique pairs (Q1,C1) and (Q2,C1)
        pair_keys = {tuple(sorted(p.members)) for p in proposals}
        self.assertEqual(pair_keys, {("C1", "Q1"), ("C1", "Q2")})


class RankByNeedTests(unittest.TestCase):
    def test_need_match_boosts_score(self):
        a = SynergyProposal(
            members=["Q1", "C1"], member_types=["BJT_NPN", "electrolytic_cap"],
            synergy_effect="Vbe + ESR", proposed_function="thermal_array",
            repurpose_application="thermal_array", confidence=0.5, notes="",
        )
        b = SynergyProposal(
            members=["X", "Y"], member_types=["a", "b"],
            synergy_effect="", proposed_function="unrelated",
            repurpose_application="unrelated", confidence=0.5, notes="",
        )
        ranked = rank_synergies_by_need([b, a], system_needs=["thermal"])
        # a wins because "thermal" matches its proposed_function
        self.assertIs(ranked[0], a)


class MultiFailureScenarioTests(unittest.TestCase):
    def test_components_degrade_on_schedule(self):
        s = MultiFailureSynergyRequired(max_ticks=200)
        for _ in range(40):
            s.step()
        # Q1 starts degrading at tick 5, rate 0.025 → at tick 39 (40 steps)
        # severity ≈ min(1.0, 0.025 * 35) = 0.875 (capped behavior verified)
        self.assertGreater(s.components_spec["Q1"]["current_severity"], 0.5)

    def test_no_intervention_eventually_fails(self):
        s = MultiFailureSynergyRequired(max_ticks=200)
        for _ in range(200):
            st = s.step()
        # All four primary components hit failed → no synergies formed → failed
        self.assertEqual(st.actual_outcome["system_state"], "failed")
        self.assertEqual(st.actual_outcome["channels_count"], 0)

    def test_lc_tank_intervention_forms_rf_channel(self):
        s = MultiFailureSynergyRequired(max_ticks=200)
        for _ in range(20):
            s.step()
        s.receive_intervention("form_lc_tank_C1_L1", 20)
        st = s.step()
        self.assertTrue(st.actual_outcome["rf_channel_formed"])
        self.assertEqual(st.actual_outcome["channels_count"], 1)

    def test_three_formations_yield_three_channels(self):
        s = MultiFailureSynergyRequired(max_ticks=200)
        for _ in range(30):
            s.step()
        s.receive_intervention("form_lc_tank_C1_L1", 30)
        s.receive_intervention("form_temp_array_Q1_D1", 31)
        s.receive_intervention("form_optical_LED1_R_failed", 32)
        st = s.step()
        self.assertEqual(st.actual_outcome["channels_count"], 3)

    def test_single_reroute_is_noop(self):
        """Single-component reroutes have no effect — scenario design."""
        s = MultiFailureSynergyRequired(max_ticks=200)
        for _ in range(20):
            s.step()
        s.receive_intervention("reroute_load_Q1_to_spare", 20)
        st = s.step()
        self.assertEqual(st.actual_outcome["channels_count"], 0)


if __name__ == "__main__":
    unittest.main()
