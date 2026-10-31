"""Tests for the noise-precursor claim and validator.

Co-authored (Kavik + Claude, 2026-10-31). CC0. Synthetic / hand-built reports only.
"""

import os
import unittest

from scenario_engine.claims import ClaimRejected
from scenario_engine.claims.noise_precursor import (
    OUTCOMES, build_noise_precursor_claim, load_noise_precursor_claims, locate_noise_row,
)
from scenario_engine.validators import validate_noise_precursor
from src import noise_titration as nt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATRICES = os.path.join(ROOT, "matrices")
ROW = {"matrix": "failure_mode_matrix", "row_index": 17,
       "component": "Diode (LED)", "failure_mode": "Reduced Light Output"}


def claim(rise=100.0, lead=1000, persist=2, tol=0.5):
    return build_noise_precursor_claim("np_test", rise_pct=rise, lead_ticks=lead, tolerance=tol,
                                       persist_windows=persist, source_matrix_row=ROW)


def report(means, rises, stable=None, W=1000, baseline=2, nominal=100.0):
    """Hand-built report: one window per entry."""
    stable = stable or [True] * len(means)
    ws = [{"start": i * W, "tick": i * W + W - 1, "mean": m, "residual_rise_pct": r, "stable": s}
          for i, (m, r, s) in enumerate(zip(means, rises, stable))]
    return {"params": {"baseline_windows": baseline}, "nominal": nominal, "windows": ws}


class ClaimBuildTests(unittest.TestCase):
    def test_well_formed(self):
        c = claim()
        self.assertEqual(c["outcome_vocabulary"], list(OUTCOMES))
        self.assertIn("at least 100% at least 1000 ticks", c["statement"])
        self.assertEqual(c["source_matrix_row"]["row_index"], 17)

    def test_rejects_missing_or_bad_parameters(self):
        with self.assertRaises(ClaimRejected):
            build_noise_precursor_claim("x", 0, 10, ROW, tolerance=1.0)
        with self.assertRaises(ClaimRejected):
            build_noise_precursor_claim("x", 50, -1, ROW, tolerance=1.0)
        with self.assertRaises(ClaimRejected):
            build_noise_precursor_claim("x", 50, 10, ROW)
        with self.assertRaises(ClaimRejected):
            build_noise_precursor_claim("x", 50, 10, ROW, tolerance=1.0, tolerance_pct=1.0)
        with self.assertRaises(ClaimRejected):
            build_noise_precursor_claim("x", 50, 10, {"matrix": "failure_mode_matrix"}, tolerance=1.0)

    def test_stored_claim_matches_matrix_row(self):
        stored = load_noise_precursor_claims()
        self.assertTrue(stored)
        for c in stored:
            src = c["source_matrix_row"]
            live = locate_noise_row(MATRICES, src["component"], src["failure_mode"])
            self.assertEqual(src, live)
            self.assertIn("ILLUSTRATIVE", c["provenance"]["parameters_origin"])
            self.assertEqual(c["status"], "pending")


class ValidatorOutcomeTests(unittest.TestCase):
    def test_confirmed(self):
        # baseline 2, rise at windows 2-3 (persist 2 -> rise_tick 3999), exit at window 6 (start 6000)
        r = report([100, 100, 100, 100, 100, 100, 101], [0, 0, 150, 150, 150, 150, 150])
        v = validate_noise_precursor(claim(lead=2000), r)
        self.assertEqual(v["outcome"], "CONFIRMED")
        self.assertEqual(v["rise_tick"], 3999)
        self.assertEqual(v["earliest_exit_tick"], 6000)
        self.assertEqual(v["lead_ticks"], 2001)
        self.assertEqual(v["source_matrix_row"], ROW)

    def test_refuted_no_rise(self):
        r = report([100, 100, 100, 100, 101], [0, 0, 10, 20, 30])
        self.assertEqual(validate_noise_precursor(claim(), r)["outcome"], "REFUTED")

    def test_refuted_lead_too_short(self):
        r = report([100, 100, 100, 100, 100, 101], [0, 0, 0, 150, 150, 150])
        v = validate_noise_precursor(claim(lead=5000), r)
        self.assertEqual(v["outcome"], "REFUTED")

    def test_inconclusive_within_window_resolution(self):
        # rise_tick 4999, exit window 6: start 6000, end 6999 -> lead 1001..2000; N = 1500
        r = report([100, 100, 100, 100, 100, 100, 101], [0, 0, 0, 150, 150, 150, 150])
        v = validate_noise_precursor(claim(lead=1500), r)
        self.assertEqual(v["outcome"], "INCONCLUSIVE")
        self.assertEqual((v["lead_ticks"], v["lead_ticks_upper"]), (1001, 2000))

    def test_unstable_rise_does_not_count(self):
        r = report([100, 100, 100, 100, 100, 101], [0, 0, 150, 150, 150, 150],
                   stable=[True, True, False, False, False, False])
        self.assertEqual(validate_noise_precursor(claim(lead=0), r)["outcome"], "REFUTED")

    def test_persist_resists_single_spike(self):
        r = report([100, 100, 100, 100, 100, 101], [0, 0, 150, 0, 150, 0])
        self.assertEqual(validate_noise_precursor(claim(lead=0), r)["outcome"], "REFUTED")

    def test_inconclusive_no_exit(self):
        r = report([100] * 6, [0, 0, 150, 150, 150, 150])
        v = validate_noise_precursor(claim(), r)
        self.assertEqual(v["outcome"], "INCONCLUSIVE")
        self.assertIn("never left tolerance", v["notes"])

    def test_inconclusive_baseline_out_of_tolerance(self):
        r = report([101, 100, 100, 101], [0, 0, 150, 150])
        self.assertEqual(validate_noise_precursor(claim(), r)["outcome"], "INCONCLUSIVE")

    def test_inconclusive_report_error(self):
        v = validate_noise_precursor(claim(), {"error": "series too short"})
        self.assertEqual(v["outcome"], "INCONCLUSIVE")

    def test_tolerance_pct_uses_nominal(self):
        c = build_noise_precursor_claim("p", 100.0, 0, ROW, tolerance_pct=0.5, persist_windows=1)
        r = report([100, 100, 100, 100.6], [0, 0, 150, 150])
        self.assertEqual(validate_noise_precursor(c, r)["outcome"], "CONFIRMED")

    def test_ignores_report_flag(self):
        r = report([100, 100, 100, 101], [0, 0, 10, 10])
        for w in r["windows"]:
            w["flag"] = True
        self.assertEqual(validate_noise_precursor(claim(lead=0), r)["outcome"], "REFUTED")


class SyntheticEndToEndTests(unittest.TestCase):
    """ILLUSTRATIVE: synthetic series through analyze() and the stored claim."""

    @classmethod
    def setUpClass(cls):
        cls.c = load_noise_precursor_claims()[0]

    def run_case(self, **kw):
        rep = nt.analyze(nt.synthetic(**kw), tolerance_pct=0.5)
        return validate_noise_precursor(self.c, rep, data_class="synthetic")

    def test_rising_1f_confirmed(self):
        v = self.run_case(flicker_end=0.25, drift_end=1.2)
        self.assertEqual(v["outcome"], "CONFIRMED")
        self.assertIn("ILLUSTRATIVE", v["notes"])

    def test_drift_only_refuted(self):
        self.assertEqual(self.run_case(flicker_end=0.01, drift_end=1.2)["outcome"], "REFUTED")

    def test_healthy_inconclusive(self):
        self.assertEqual(self.run_case(flicker_end=0.01, drift_end=0.0)["outcome"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
