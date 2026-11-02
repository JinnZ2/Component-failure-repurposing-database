"""Offline tests for scripts/fetch_ims_bearings.py and scripts/real_data_titration.py.

Co-authored (2026-10-31). CC0.
No network. Fixtures are MOCK: synthetic values in the same file shape as the IMS snapshots
(tab-separated rows, one column per channel, timestamp file names). They are not IMS data;
the data set's license is not verified, so no real slice is committed.
"""

import datetime
import hashlib
import importlib.util
import io
import os
import random
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FETCH = _load("fetch_ims_bearings")
RDT = _load("real_data_titration")

def mock_snapshot(rng, n_rows, n_ch, scale=0.1):
    return "\n".join("\t".join("%.3f" % rng.gauss(0, scale) for _ in range(n_ch)) for _ in range(n_rows))


class PreregistrationTests(unittest.TestCase):
    def test_prereg_values_pinned(self):
        P = RDT.PREREG
        self.assertEqual((P["baseline_frac"], P["k_sd"], P["rise_pct"], P["lead_ticks"], P["persist"],
                          P["smooth"], P["samples_per_snapshot"]),
                         (0.10, 3.0, 100.0, 6, 3, 5, 20480))
        self.assertEqual(P["levels"], [0.0, 0.5, 1.0, 2.0])
        self.assertEqual(P["set3_readme_end"], "2004.04.04.19.01.57")
        self.assertEqual(P["failed"], {"1": {"3": "inner race defect", "4": "roller element defect"},
                                       "2": {"1": "outer race failure"}, "3": {"3": "outer race failure"}})
        self.assertEqual(P["matrix_row"], ["Motor", "Bearing Failure"])
        self.assertEqual(P["baseline_stats_from"], "raw")

    def test_changes_logged_mark_exploratory(self):
        # an empty CHANGES list is what makes a result PRE-REGISTERED
        self.assertIsInstance(RDT.CHANGES, list)

    def test_matrix_row_exists(self):
        from scenario_engine.claims.noise_precursor import locate_noise_row
        row = locate_noise_row(os.path.join(ROOT, "matrices"), *RDT.PREREG["matrix_row"])
        self.assertEqual(row["noise_signature_status"], "OBSERVED")


class LoaderTests(unittest.TestCase):
    def test_parse_snapshot_shape(self):
        chans = RDT.parse_snapshot("0.1\t-0.2\t0.3\t0.4\n-0.5\t0.6\t0.7\t0.8\n", 4)
        self.assertEqual([len(c) for c in chans], [2, 2, 2, 2])
        self.assertEqual(chans[1], [-0.2, 0.6])

    def test_parse_snapshot_rejects_wrong_width(self):
        with self.assertRaises(ValueError):
            RDT.parse_snapshot("0.1\t0.2\n", 4)

    def test_snapshot_time(self):
        t = RDT.snapshot_time("/x/2004.02.12.10.32.39")
        self.assertEqual((t.year, t.month, t.day, t.hour, t.minute, t.second), (2004, 2, 12, 10, 32, 39))

    def test_set3_truncated_to_readme_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "4th_test", "txt")
            os.makedirs(d)
            for n in ("2004.04.04.18.51.57", "2004.04.04.19.01.57", "2004.04.04.19.11.57"):
                open(os.path.join(d, n), "w").close()
            names = [os.path.basename(p) for p in RDT.list_snapshots(3, tmp)]
            self.assertEqual(names, ["2004.04.04.18.51.57", "2004.04.04.19.01.57"])

    def test_units_and_failure_labels(self):
        u1 = RDT.units(1)
        self.assertEqual([u["unit"] for u in u1[4:6]], ["s1_b3x", "s1_b3y"])
        self.assertEqual(u1[4]["failed"], "inner race defect")
        self.assertIsNone(RDT.units(2)[1]["failed"])

    def test_snapshot_features_on_mock_file(self):
        rng = random.Random(1)
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "2004.02.12.10.32.39")
            with open(p, "w") as f:
                f.write(mock_snapshot(rng, 2048, 4))
            _, base = RDT.snapshot_features((2, 0, p, None))
            self.assertEqual(len(base), 4)
            _, feats = RDT.snapshot_features((2, 0, p, [0.1] * 4))
            self.assertAlmostEqual(feats[0]["rms"], 0.1, delta=0.01)
            self.assertAlmostEqual(feats[0]["kurtosis"], 3.0, delta=0.4)


class AnalysisLogicTests(unittest.TestCase):
    """MOCK per-snapshot feature series, built by hand."""

    def series(self, n=100, res_rise_at=None, rms_rise_at=None, kur_rise_at=None):
        rng = random.Random(2)
        ch = []
        for i in range(n):
            ch.append({"rms": 1.0 + rng.gauss(0, 0.01) + (0.5 if rms_rise_at is not None and i >= rms_rise_at else 0),
                       "kurtosis": 3.0 + rng.gauss(0, 0.05) + (3 if kur_rise_at is not None and i >= kur_rise_at else 0),
                       "residual": 1e-3 * (1 + rng.gauss(0, 0.05)) * (5 if res_rise_at is not None and i >= res_rise_at else 1),
                       "white": 1e-2, "stable": True})
        t0 = datetime.datetime(2004, 2, 12, 10, 0, 0)
        times = [(t0 + datetime.timedelta(minutes=10 * i)).strftime("%Y.%m.%d.%H.%M.%S") for i in range(n)]
        return ch, times

    def test_titration_first_confirmed(self):
        ch, times = self.series(res_rise_at=40, rms_rise_at=70, kur_rise_at=60)
        an = RDT.analyse_unit(ch, times, nb=10)
        al = an["alarms"]
        self.assertLess(al["titration"], al["kurtosis"])
        self.assertLess(al["kurtosis"], al["rms"])
        self.assertEqual(RDT.grade_unit(an, "mock")["outcome"], "CONFIRMED")

    def test_rms_first_refuted(self):
        ch, times = self.series(res_rise_at=None, rms_rise_at=50)
        an = RDT.analyse_unit(ch, times, nb=10)
        self.assertIsNone(an["alarms"]["titration"])
        self.assertEqual(RDT.grade_unit(an, "mock")["outcome"], "REFUTED")

    def test_no_failure_side_event_inconclusive(self):
        ch, times = self.series()
        self.assertEqual(RDT.grade_unit(RDT.analyse_unit(ch, times, nb=10), "mock")["outcome"], "INCONCLUSIVE")

    def test_unstable_residual_ignored(self):
        ch, times = self.series(res_rise_at=40, rms_rise_at=70)
        for f in ch:
            f["stable"] = False
        self.assertIsNone(RDT.analyse_unit(ch, times, nb=10)["alarms"]["titration"])

    def test_lead_in_hours(self):
        ch, times = self.series(rms_rise_at=94)
        an = RDT.analyse_unit(ch, times, nb=10)
        # step at 94 -> trailing median of 5 high from 96 -> third consecutive at 98
        self.assertEqual(an["alarms"]["rms"], 98)
        self.assertEqual(an["leads"]["rms"]["snapshots"], 99 - 98)
        self.assertEqual(an["leads"]["rms"]["hours"], 0.2)


class FetchScriptTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(FETCH.URL, "https://phm-datasets.s3.amazonaws.com/NASA/4.+Bearings.zip")
        self.assertEqual(len(FETCH.ZIP_SHA256), 64)
        self.assertEqual(FETCH.README_COUNTS, {"1st_test": 2156, "2nd_test": 984, "4th_test": 4448})

    def test_checksum_mismatch_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "f")
            with open(p, "wb") as f:
                f.write(b"abc")
            self.assertEqual(FETCH.sha256_file(p), hashlib.sha256(b"abc").hexdigest())
            with self.assertRaises(SystemExit):
                FETCH.check_zip(p)

    def test_download_with_fake_opener(self):
        payload = b"x" * 1000

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        seen = {}

        def opener(req, timeout=None):
            seen["range"] = req.headers.get("Range")
            return Resp(payload)

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "z.zip")
            FETCH.download(url="http://mock.invalid/z.zip", dest=dest, opener=opener)
            self.assertEqual(open(dest, "rb").read(), payload)
            self.assertIsNone(seen["range"])
            FETCH.download(url="http://mock.invalid/z.zip", dest=dest, opener=opener)  # resume
            self.assertEqual(seen["range"], "bytes=1000-")

    def test_snapshot_counts_nested(self):
        with tempfile.TemporaryDirectory() as tmp:
            for d, n in (("2nd_test", 3), ("4th_test/txt", 2)):
                os.makedirs(os.path.join(tmp, "extracted", d))
                for i in range(n):
                    open(os.path.join(tmp, "extracted", d, str(i)), "w").close()
            self.assertEqual(FETCH.snapshot_counts(tmp), {"2nd_test": 3, "4th_test": 2})

    def test_missing_libarchive_is_reported(self):
        orig = FETCH.ctypes.util.find_library
        FETCH.ctypes.util.find_library = lambda n: None
        try:
            with self.assertRaises(SystemExit) as cm:
                FETCH.LibArchive()
            self.assertIn("libarchive", str(cm.exception))
        finally:
            FETCH.ctypes.util.find_library = orig

    def test_zip_member_read_with_stdlib(self):
        with tempfile.TemporaryDirectory() as tmp:
            zp = os.path.join(tmp, "b.zip")
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr(FETCH.ZIP_MEMBER, b"7z\xbc\xaf'\x1c MOCK")
            with zipfile.ZipFile(zp) as z:
                self.assertTrue(z.read(FETCH.ZIP_MEMBER).startswith(b"7z"))


if __name__ == "__main__":
    unittest.main()
