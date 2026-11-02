#!/usr/bin/env python3
"""
real_data_titration.py -- first real-data run of src/noise_titration.py: IMS bearings.

Co-authored (2026-10-31). CC0 for this script; the IMS data keeps its own
license (data/README_ims_bearings.md). Stdlib only (data extraction: scripts/fetch_ims_bearings.py).

Question: does the titration residual rise while the vibration level is still inside its
baseline band, and does it add anything over plain RMS and kurtosis?

PRE-REGISTERED 2026-10-31, written before any residual, RMS or kurtosis value was computed on
IMS data. The values are frozen in PREREG below; tests/ pins them. Any change after seeing an
outcome is appended to CHANGES with a reason, and the result is then marked EXPLORATORY.

  data        sets 1, 2, 3 as delivered (scripts/fetch_ims_bearings.py). Set 3 = the 4448
              snapshots inside the readme's stated window (up to 2004.04.04.19.01.57); the
              1876 delivered snapshots after it are not analysed (mismatch recorded).
  units       every channel. Set 1: 8 channels, 2 per bearing (x, y). Sets 2, 3: 1 per bearing.
  failed      per the data set's readme: set 1 bearing 3 (inner race) and bearing 4 (roller
              element); set 2 bearing 1 (outer race); set 3 bearing 3 (outer race). All other
              bearings: not reported failed.
  snapshot    all 20480 samples of the channel (1 s at 20 kHz).
  per snapshot RMS (mean removed); kurtosis m4 / m2^2 (non-excess); titration residual h and
              stable flag from noise_titration.titrate_window(levels 0, 0.5, 1, 2;
              stability_tol 0.5; rng seeded by (set, snapshot index, channel)).
  sigma_ref   per channel: sqrt(median white term a) over the baseline snapshots.
  smoothing   trailing median of 5 snapshots on RMS, kurtosis and h.
  baseline    first 10% of the set's snapshots (int(0.1 * n)).
  tolerance   "mean leaves tolerance" = smoothed RMS outside mu_RMS +/- 3 * sd_RMS, mu and
              sd over the baseline RAW (unsmoothed) RMS. First such post-baseline snapshot = exit.
  claim       build_noise_precursor_claim(rise_pct X = 100, lead_ticks N = 6 snapshots,
              tolerance = 3 * sd_RMS absolute, persist_windows = 3), source_matrix_row =
              failure_mode_matrix (Motor, Bearing Failure). Graded by
              validators.noise_precursor. Residual rise % = (h_smoothed - h_base) / denom * 100,
              h_base = median baseline h, denom = max(h_base, 0.01 * median baseline a).
  comparators alarm = first post-baseline snapshot where the smoothed statistic exceeds
              mu + 3 * sd of its RAW baseline values for 3 consecutive snapshots. Applied to RMS and to
              kurtosis. Titration alarm = residual rise >= 100%, stable, 3 consecutive.
              Lead = time from alarm to the set's last snapshot (snapshots and hours).
  reading     titration adds something on a failed unit if its alarm comes before both the
              RMS and the kurtosis alarm. Any alarm on a unit not reported failed is listed
              as an alarm on a non-failed unit (not resolved as false: the readme does not
              say those bearings were undamaged).

  revision 1  2026-10-31, still before any IMS value was computed: mu and sd were first taken
              over the SMOOTHED baseline. Measured on i.i.d. Gaussian noise (200 series each,
              lengths 984 / 2156 / 4448, baseline 10%, trailing median 5, 3 consecutive): that
              rule raised an alarm on 27% / 37% / 53% of pure-noise series; with mu and sd
              from the RAW baseline values: 0% / 0% / 0%. Changed to raw. Not an outcome-driven
              change (no outcome existed), so it is recorded here, not in CHANGES.

SCOPE: one rig, 3 tests, 4 failed bearings. A result here is real data, not a general result.

USAGE
  python3 scripts/real_data_titration.py --features   compute per-snapshot features (cached)
  python3 scripts/real_data_titration.py --report     analysis + results/real_data_titration_ims_bearings.md
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

import noise_titration as nt  # noqa: E402

DATA = os.path.join(ROOT, "data", "external", "ims_bearings")
EXTRACTED = os.path.join(DATA, "extracted")
RESULTS = os.path.join(ROOT, "results", "real_data_titration_ims_bearings.md")

PREREG = {
    "date": "2026-10-31",
    "set_dirs": {"1": "1st_test", "2": "2nd_test", "3": "4th_test/txt"},
    "set3_readme_end": "2004.04.04.19.01.57",
    "channels": {"1": 8, "2": 4, "3": 4},
    "channel_bearing": {"1": [1, 1, 2, 2, 3, 3, 4, 4], "2": [1, 2, 3, 4], "3": [1, 2, 3, 4]},
    "failed": {"1": {"3": "inner race defect", "4": "roller element defect"},
               "2": {"1": "outer race failure"},
               "3": {"3": "outer race failure"}},
    "samples_per_snapshot": 20480,
    "levels": [0.0, 0.5, 1.0, 2.0],
    "stability_tol": 0.5,
    "smooth": 5,
    "baseline_frac": 0.10,
    "k_sd": 3.0,
    "rise_pct": 100.0,
    "lead_ticks": 6,
    "persist": 3,
    "floor_frac": 0.01,
    "matrix_row": ["Motor", "Bearing Failure"],
    "baseline_stats_from": "raw",
}
CHANGES = []  # (date, change, reason); non-empty -> EXPLORATORY


def prereg_sha256():
    return hashlib.sha256(json.dumps(PREREG, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ loading

def parse_snapshot(text, n_channels):
    """Tab/space separated rows -> list of channel lists."""
    chans = [[] for _ in range(n_channels)]
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if len(parts) != n_channels:
            raise ValueError("row has %d values, expected %d" % (len(parts), n_channels))
        for c, v in enumerate(parts):
            chans[c].append(float(v))
    return chans


def snapshot_time(name):
    return datetime.datetime.strptime(os.path.basename(name), "%Y.%m.%d.%H.%M.%S")


def list_snapshots(set_no, root=EXTRACTED):
    d = os.path.join(root, PREREG["set_dirs"][str(set_no)])
    names = sorted(os.listdir(d))
    if set_no == 3:
        names = [n for n in names if n <= PREREG["set3_readme_end"]]
    return [os.path.join(d, n) for n in names]


# ------------------------------------------------------------------ per-snapshot features

def rms_kurtosis(x):
    n = len(x)
    m = sum(x) / n
    m2 = sum((v - m) ** 2 for v in x) / n
    m4 = sum((v - m) ** 4 for v in x) / n
    return math.sqrt(m2), (m4 / (m2 * m2) if m2 > 0 else 0.0)


def white_level(x):
    f = nt.fit_noise_model(nt.detrend(x), nt.scales_for(len(x)))
    return max(f["a"], 0.0) if f else 0.0


def snapshot_features(args):
    """Worker: (set_no, idx, path, sigma_refs or None) -> per-channel features."""
    set_no, idx, path, sigma_refs = args
    nch = PREREG["channels"][str(set_no)]
    with open(path, encoding="ascii") as fh:
        chans = parse_snapshot(fh.read(), nch)
    out = []
    for c, x in enumerate(chans):
        x = x[:PREREG["samples_per_snapshot"]]
        if sigma_refs is None:
            out.append({"white": white_level(x)})
            continue
        rms, kurt = rms_kurtosis(x)
        rng = random.Random(set_no * 10 ** 7 + idx * 10 + c)
        t = nt.titrate_window(x, sigma_refs[c], tuple(PREREG["levels"]), rng, PREREG["stability_tol"])
        out.append({"rms": rms, "kurtosis": kurt,
                    "residual": None if t is None else t["residual"],
                    "white": None if t is None else t["white"],
                    "stable": bool(t and t["stable"])})
    return idx, out


def compute_features(set_no, procs=None, root=EXTRACTED):
    import multiprocessing as mp
    paths = list_snapshots(set_no, root)
    nb = int(PREREG["baseline_frac"] * len(paths))
    nch = PREREG["channels"][str(set_no)]
    with mp.Pool(procs) as pool:
        base = dict(pool.map(snapshot_features, [(set_no, i, p, None) for i, p in enumerate(paths[:nb])]))
        sigma = [math.sqrt(nt.median([base[i][c]["white"] for i in range(nb)])) for c in range(nch)]
        feats = dict(pool.map(snapshot_features, [(set_no, i, p, sigma) for i, p in enumerate(paths)],
                              chunksize=8))
    return {"set": set_no, "n": len(paths), "baseline_n": nb, "sigma_ref": sigma,
            "times": [os.path.basename(p) for p in paths],
            "channels": [[feats[i][c] for i in range(len(paths))] for c in range(nch)],
            "prereg_sha256": prereg_sha256()}


# ------------------------------------------------------------------ analysis

def trailing_median(xs, k):
    out = []
    for i in range(len(xs)):
        w = [v for v in xs[max(0, i - k + 1):i + 1] if v is not None]
        out.append(nt.median(w) if w else None)
    return out


def mean_sd(xs):
    xs = [v for v in xs if v is not None]
    m = sum(xs) / len(xs)
    return m, math.sqrt(sum((v - m) ** 2 for v in xs) / len(xs))


def first_sustained(flags, start, persist):
    run = 0
    for i in range(start, len(flags)):
        run = run + 1 if flags[i] else 0
        if run >= persist:
            return i
    return None


def analyse_unit(ch, times, nb, P=PREREG):
    """ch: list of per-snapshot feature dicts. Returns dict with report + alarms."""
    k = P["smooth"]
    rms = trailing_median([f["rms"] for f in ch], k)
    kur = trailing_median([f["kurtosis"] for f in ch], k)
    res = trailing_median([f["residual"] for f in ch], k)
    mu_r, sd_r = mean_sd([f["rms"] for f in ch[:nb]])       # raw baseline (revision 1)
    mu_k, sd_k = mean_sd([f["kurtosis"] for f in ch[:nb]])
    h_base = nt.median([v for v in res[:nb] if v is not None])
    a_base = nt.median([f["white"] for f in ch[:nb] if f["white"] is not None])
    denom = max(h_base, P["floor_frac"] * a_base, 1e-30)
    rise = [None if v is None else (v - h_base) / denom * 100.0 for v in res]
    windows = [{"start": i, "tick": i, "mean": rms[i], "residual_rise_pct": rise[i],
                "stable": ch[i]["stable"]} for i in range(len(ch))]
    report = {"params": {"baseline_windows": nb}, "nominal": mu_r, "windows": windows}
    tol = P["k_sd"] * sd_r
    a_rms = first_sustained([v > mu_r + tol for v in rms], nb, P["persist"])
    a_kur = first_sustained([v > mu_k + P["k_sd"] * sd_k for v in kur], nb, P["persist"])
    a_tit = first_sustained([r is not None and r >= P["rise_pct"] and ch[i]["stable"]
                             for i, r in enumerate(rise)], nb, P["persist"])
    end = len(ch) - 1
    t_end = snapshot_time(times[end])

    def lead(i):
        if i is None:
            return None
        return {"snapshots": end - i,
                "hours": round((t_end - snapshot_time(times[i])).total_seconds() / 3600.0, 1)}

    return {"report": report, "tolerance": tol, "mu_rms": mu_r, "sd_rms": sd_r,
            "h_base": h_base, "alarms": {"titration": a_tit, "rms": a_rms, "kurtosis": a_kur},
            "leads": {"titration": lead(a_tit), "rms": lead(a_rms), "kurtosis": lead(a_kur)}}


def grade_unit(analysis, unit_id, matrices=os.path.join(ROOT, "matrices")):
    from scenario_engine.claims.noise_precursor import build_noise_precursor_claim, locate_noise_row
    from scenario_engine.validators.noise_precursor import validate_noise_precursor
    row = locate_noise_row(matrices, *PREREG["matrix_row"])
    claim = build_noise_precursor_claim(
        "noise_precursor_ims_" + unit_id, rise_pct=PREREG["rise_pct"], lead_ticks=PREREG["lead_ticks"],
        tolerance=analysis["tolerance"], persist_windows=PREREG["persist"], source_matrix_row=row,
        provenance={"data": "IMS bearings, real run-to-failure data", "prereg_sha256": prereg_sha256(),
                    "exploratory": bool(CHANGES)})
    return validate_noise_precursor(claim, analysis["report"], data_class="field")


def units(set_no):
    nch = PREREG["channels"][str(set_no)]
    cb = PREREG["channel_bearing"][str(set_no)]
    failed = PREREG["failed"][str(set_no)]
    out = []
    for c in range(nch):
        b = cb[c]
        axis = ("x" if c % 2 == 0 else "y") if nch == 8 else ""
        out.append({"channel": c, "bearing": b, "unit": "s%d_b%d%s" % (set_no, b, axis),
                    "failed": failed.get(str(b))})
    return out


def features_path(set_no):
    return os.path.join(DATA, "features_set%d.json" % set_no)


def fmt_lead(l):
    return "-" if l is None else "%d / %.1f h" % (l["snapshots"], l["hours"])


def build_rows(feats_by_set):
    rows = []
    for set_no in sorted(feats_by_set):
        F = feats_by_set[set_no]
        for u in units(set_no):
            an = analyse_unit(F["channels"][u["channel"]], F["times"], F["baseline_n"])
            v = grade_unit(an, u["unit"])
            rows.append({"unit": u["unit"], "failed": u["failed"], "analysis": an, "verdict": v})
    return rows


def write_report(rows, path=RESULTS):
    status = "EXPLORATORY" if CHANGES else "PRE-REGISTERED"
    L = ["# Real-data titration: IMS bearing run-to-failure data", "",
         "Co-authored, 2026-10-31. CC0 (this write-up; the data keeps its own license).",
         "REAL DATA (not synthetic). Status: **%s** (prereg sha256 `%s`)." % (status, prereg_sha256()), "",
         "| unit | failed? | flag fired? | lead (snapshots / hours) | RMS lead | kurtosis lead | outcome |",
         "|---|---|---|---|---|---|---|"]
    for r in rows:
        a = r["analysis"]
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["unit"], r["failed"] or "no", "yes" if a["alarms"]["titration"] is not None else "no",
            fmt_lead(a["leads"]["titration"]), fmt_lead(a["leads"]["rms"]), fmt_lead(a["leads"]["kurtosis"]),
            r["verdict"]["outcome"]))
    L += ["", "Lead = time from alarm to the set's last snapshot. Outcome = noise_precursor validator "
          "(residual rise >= 100% at least 6 snapshots before smoothed RMS leaves mu +/- 3 sd).", ""]
    L += ["## Validator detail", "", "```text"]
    for r in rows:
        v = r["verdict"]
        L.append("%-10s %-12s rise_tick=%s exit_tick=%s lead=%s..%s  %s" % (
            r["unit"], v["outcome"], v.get("rise_tick"), v.get("mean_exit_tick"), v.get("lead_ticks"),
            v.get("lead_ticks_upper"), v["notes"]))
    L += ["```", "", "## Changes after pre-registration", ""]
    L += ["- none"] if not CHANGES else ["- %s: %s (%s)" % c for c in CHANGES]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--sets", default="1,2,3")
    ap.add_argument("--procs", type=int)
    a = ap.parse_args(argv)
    sets = [int(s) for s in a.sets.split(",")]
    print("prereg sha256", prereg_sha256(), "| changes:", len(CHANGES))
    if a.features:
        for s in sets:
            F = compute_features(s, a.procs)
            with open(features_path(s), "w") as fh:
                json.dump(F, fh)
            print("set", s, "snapshots", F["n"], "baseline", F["baseline_n"])
    if a.report:
        feats = {}
        for s in sets:
            with open(features_path(s)) as fh:
                feats[s] = json.load(fh)
        print("wrote", write_report(build_rows(feats)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
