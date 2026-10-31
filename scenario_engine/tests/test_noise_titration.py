"""Tests for src/noise_titration.py and the failure_mode_matrix noise columns.

Co-authored (Kavik + Claude, 2026-10-31). CC0. Synthetic data only (ILLUSTRATIVE).
"""

import csv
import os
import random
import re
import unittest

from src import noise_titration as nt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATRIX = os.path.join(ROOT, "matrices", "failure_mode_matrix.csv")


class AllanAndFitTests(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(3)

    def test_white_allan_variance_scales_as_one_over_m(self):
        w = [self.rng.gauss(0, 1) for _ in range(65536)]
        av1, _ = nt.allan_variance(w, 1)
        av16, _ = nt.allan_variance(w, 16)
        self.assertAlmostEqual(av1, 1.0, delta=0.05)
        self.assertAlmostEqual(av16 * 16, 1.0, delta=0.15)

    def test_allan_needs_two_blocks(self):
        self.assertEqual(nt.allan_variance([1.0, 2.0, 3.0], 2), (None, 0))

    def test_fit_white_only_has_near_zero_floor(self):
        w = [self.rng.gauss(0, 1) for _ in range(8192)]
        f = nt.fit_noise_model(w, nt.scales_for(8192))
        self.assertLess(abs(f["h"] / f["a"]), 0.01)

    def test_fit_pink_has_floor_above_white(self):
        pk = [0.3 * v + self.rng.gauss(0, 0.05) for v in nt.pink_noise(8192, self.rng)]
        f = nt.fit_noise_model(pk, nt.scales_for(8192))
        self.assertGreater(f["h"] / f["a"], 1.0)

    def test_detrend_removes_line(self):
        y = nt.detrend([2.0 * i + 5 for i in range(100)])
        self.assertLess(max(abs(v) for v in y), 1e-9)


class TitrationTests(unittest.TestCase):
    def test_injection_lands_in_white_term(self):
        rng = random.Random(5)
        pk = [0.3 * v + rng.gauss(0, 0.05) for v in nt.pink_noise(2048, rng)]
        t = nt.titrate_window(pk, 0.05, (0, 0.5, 1, 2), random.Random(0), 0.5)
        self.assertGreater(t["injection_recovery"], 0.6)
        self.assertLess(t["injection_recovery"], 1.4)
        self.assertTrue(t["stable"])

    def test_white_only_residual_not_stable(self):
        rng = random.Random(6)
        t = nt.titrate_window([rng.gauss(0, 1) for _ in range(2048)], 1.0,
                              (0, 0.5, 1, 2), random.Random(0), 0.5)
        self.assertFalse(t["stable"])

    def test_deterministic(self):
        r1 = nt.analyze(nt.synthetic(seed=4), tolerance=0.5)
        r2 = nt.analyze(nt.synthetic(seed=4), tolerance=0.5)
        self.assertEqual(r1, r2)


class DemoBehaviourTests(unittest.TestCase):
    """ILLUSTRATIVE synthetic runs: show the method behaves as specified, nothing more."""

    @classmethod
    def setUpClass(cls):
        cls.healthy = nt.analyze(nt.synthetic(flicker_end=0.01, drift_end=0.0), tolerance=0.5)
        cls.failing = nt.analyze(nt.synthetic(flicker_end=0.25, drift_end=1.2), tolerance=0.5)
        cls.drift_only = nt.analyze(nt.synthetic(flicker_end=0.01, drift_end=1.2), tolerance=0.5)

    def test_healthy_no_flag_no_exit(self):
        self.assertIsNone(self.healthy["first_flag_tick"])
        self.assertIsNone(self.healthy["first_mean_exit_tick"])

    def test_failing_flag_before_mean_exit(self):
        f = self.failing
        self.assertIsNotNone(f["first_flag_tick"])
        self.assertIsNotNone(f["first_mean_exit_tick"])
        self.assertLess(f["first_flag_tick"], f["first_mean_exit_tick"])

    def test_flag_only_while_mean_inside(self):
        for w in self.failing["windows"]:
            if w["flag"]:
                self.assertTrue(w["mean_inside_tolerance"])

    def test_drift_without_noise_does_not_flag(self):
        self.assertIsNone(self.drift_only["first_flag_tick"])
        self.assertIsNotNone(self.drift_only["first_mean_exit_tick"])

    def test_short_series_reports_error(self):
        self.assertIn("error", nt.analyze([1.0] * 100))

    def test_tolerance_pct(self):
        r = nt.analyze(nt.synthetic(seed=2), tolerance_pct=0.5)
        self.assertAlmostEqual(r["tolerance"], abs(r["nominal"]) * 0.005)


class MatrixNoiseColumnTests(unittest.TestCase):
    ALLOWED = {"OBSERVED", "DERIVED", "PROPOSED", "OWED"}

    @classmethod
    def setUpClass(cls):
        with open(MATRIX, encoding="utf-8", newline="") as f:
            cls.rows = list(csv.DictReader(f))
        with open(MATRIX, encoding="utf-8", newline="") as f:
            cls.header = next(csv.reader(f))

    def test_original_columns_first_then_new(self):
        self.assertEqual(self.header[:5], ["Component", "Failure Mode", "Repurpose Option",
                                           "Effectiveness", "Notes"])
        self.assertEqual(self.header[5:], ["Pre-failure noise signature", "Noise signature status"])

    def test_every_row_tagged(self):
        for r in self.rows:
            self.assertIn(r["Noise signature status"], self.ALLOWED, r)

    def test_owed_iff_not_interpretable(self):
        for r in self.rows:
            owed = r["Noise signature status"] == "OWED"
            self.assertEqual(owed, "not interpretable atm" in r["Pre-failure noise signature"], r)

    def test_filled_rows_cite_known_sources(self):
        keys = set(nt.NOISE_SOURCES)
        for r in self.rows:
            if r["Noise signature status"] == "OWED":
                continue
            cited = set()
            for bracket in re.findall(r"\[([^\]]+)\]", r["Pre-failure noise signature"]):
                for part in re.split(r"[;,]", bracket):
                    m = re.match(r"\s*([A-Z][A-Z0-9_]{5,})\b", part)
                    if m:
                        cited.add(m.group(1))
            self.assertTrue(cited, r)
            self.assertTrue(cited <= keys, (cited - keys, r))

    def test_every_source_has_check_note(self):
        for k, v in nt.NOISE_SOURCES.items():
            self.assertTrue(v.get("cite") and v.get("checked") and v.get("tag"), k)


if __name__ == "__main__":
    unittest.main()
