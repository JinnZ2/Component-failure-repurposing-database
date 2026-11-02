#!/usr/bin/env python3
"""
noise_titration.py -- noise as a DIAGNOSTIC before failure: "mean holds, noise moves first".

STATUS: PROPOSED method, co-authored (2026-10-31). CC0. stdlib only.

TWO LAYERS, KEPT APART
  Published (DOCUMENTED, see NOISE_SOURCES):
    Low-frequency (1/f, burst, generation-recombination) noise tracks quality and
    reliability of electronic devices and can change before DC parameters do
    (VANDAMME1994; device-class results in the other keys).
  PROPOSED here (untested on real components):
    Noise titration (GIULIANI_VICI2024: add known noise at increasing levels; what
    holds steady carries signal, what shifts is junk) adapted from principal
    components to a component's reading time series, to separate a 1/f residual
    from white noise and to watch that residual over time.

METHOD, per window of readings
  1. remove the linear trend; the window mean goes to the MEAN channel
  2. inject white Gaussian noise of known sigma_k = level_k * sigma_ref (seeded)
  3. Allan variance AV(m) at block sizes m = 1, 2, 4, ... ; fit
         AV(m) = a/m + h + b*m
     white noise -> a/m, flicker (1/f) -> flat h, random walk -> b*m
  4. titration reading
       a moves with the injection (slope of a_k - a_0 on sigma_k^2 ~ 1)  -> junk channel
       h is what the injection cannot explain                              -> RESIDUAL
       h holding steady across levels -> stable (real); h shifting -> not stable
  5. over windows: residual rise vs baseline, trend, and the FLAG
       residual up >= rise_pct for `persist` windows, titration-stable,
       while the window mean is still inside tolerance  ->  "mean holds, noise moves first"

USAGE
  python3 src/noise_titration.py --demo          synthetic healthy vs rising-1/f (ILLUSTRATIVE)
  python3 src/noise_titration.py --selftest      planted checks, prints count
  python3 src/noise_titration.py readings.txt --tolerance 0.5 [--json]
     readings.txt: one numeric reading per line, one component, fixed sample rate

LIMITS
  - Window must be long enough for several blocks at the largest scale; short series
    give noisy h. Defaults: window 1024, scales up to window/8.
  - Detrending per window hides drift slower than a window inside the MEAN channel only.
  - Assumes white + flicker + random walk; burst (popcorn) noise is not separately fitted
    and lands mostly in h and b. GAP.
  - Synthetic demo results are ILLUSTRATIVE, not field evidence.
"""
import argparse
import json
import math
import random
import sys

# Source keys used by matrices/failure_mode_matrix.csv "Pre-failure noise signature".
# "checked": what was verified on 2026-10-31. VERIFY = not checked word-for-word.
NOISE_SOURCES = {
    "VANDAMME1994": {
        "cite": "L.K.J. Vandamme, 'Noise as a diagnostic tool for quality and reliability of "
                "electronic devices', IEEE Trans. Electron Devices 41(11):2176-2187, 1994, "
                "doi:10.1109/16.333839",
        "checked": "bibliographic record and abstract; scope lists 1/f, burst, g-r noise, contacts, "
                   "vias, electromigration, diode-type devices. Full text VERIFY",
        "tag": "DOCUMENTED"},
    "GIULIANI_VICI2024": {
        "cite": "A. Giuliani, A. Vici, 'On the (Apparently) Paradoxical Role of Noise in the "
                "Recognition of Signal Character of Minor Principal Components', Stats 7(1):4 "
                "(pp. 54-64), 2024, doi:10.3390/stats7010004",
        "checked": "record and abstract; method = titration with added noise on principal "
                   "components. Application to component time series here is PROPOSED",
        "tag": "DOCUMENTED (method source only)"},
    "SIKULA2002": {
        "cite": "J. Sikula et al., 'Low Frequency Noise of Tantalum Capacitors', Active and "
                "Passive Electronic Components, 2002",
        "checked": "abstract: noise vs leakage correlation, noise reliability indicator, ~2 "
                   "decades spread at equal leakage. Full text VERIFY",
        "tag": "DOCUMENTED"},
    "PAVELKA_THICKFILM": {
        "cite": "J. Pavelka, M. Tacano, J. Sikula, noise spectroscopy and non-linearity of thick-film "
                "resistors and Ta/Nb capacitors as non-destructive reliability test (venue, year VERIFY)",
        "checked": "abstract-level search result only. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "GAN_LED_2005": {
        "cite": "GaN LED accelerated-aging low-frequency noise study, 2005 (authors, venue VERIFY; "
                "record found via sapientia.ualg.pt)",
        "checked": "summary: series-resistance noise rose up to 800x vs 13-90% series-resistance "
                   "rise; junction 1/f little changed. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "LED_EARLY_2011": {
        "cite": "LED noise screening paper, ojs.suitt.edu.ua, 2011 (authors VERIFY)",
        "checked": "summary: high noise or anomalous noise kinetics in first test hours -> "
                   "potentially unreliable. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "OLED_2013": {
        "cite": "'Low frequency noise as a diagnostic tool for OLED reliability', Univ. of Bath "
                "research portal, 2013 (authors, venue VERIFY)",
        "checked": "summary: robust OLEDs 1/f; unreliable show current switching events and "
                   "optical blinks. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "HC_1F_1999": {
        "cite": "n-MOSFET hot-carrier stress and 1/f noise study, 1999 (authors, venue VERIFY)",
        "checked": "summary: stress-induced 1/f rise mainly from created oxide traps. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "HC_RTS_1997": {
        "cite": "'Hot-carrier stress effects on the amplitude of random telegraph signals in "
                "small-area Si p-MOSFETs', 1997 (authors, venue VERIFY)",
        "checked": "title and summary: RTS amplitude of an oxide trap increases after stress. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "EM_NOISE": {
        "cite": "MRS proceedings 1991, 1/f^2 noise and electromigration in AlCu interconnects; "
                "Guo, Jones, Trefan, Microelectronics Reliability, 1999 (details VERIFY)",
        "checked": "summaries: pre-test noise correlated with EM failure time; 1/f -> 1/f^2 as EM "
                   "proceeds. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "CONTACT_FRETTING": {
        "cite": "Maul & McBride; Swingler & McBride (Univ. of Southampton eprints); IEEE 2012 "
                "'Leading indicators for prognostic health management of electrical connectors "
                "subjected to random vibration' (details VERIFY)",
        "checked": "summaries: resistance rise with intermittences, self-healing, resistance "
                   "spectroscopy as leading indicator. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "BEARING_VIB": {
        "cite": "rolling-bearing run-to-failure literature on vibration RMS and kurtosis, incl. "
                "FEMTO/PRONOSTIA-based studies (specific papers VERIFY)",
        "checked": "summaries: kurtosis rises with race defect, RMS near end of life; some "
                   "records show no change before failure. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "ECAP_ESR": {
        "cite": "Celaya, Kulkarni et al., NASA NTRS 20140010141, electrolytic capacitor "
                "prognostics (RC time constant precursor) (details VERIFY)",
        "checked": "summary: ESR rise / capacitance loss as degradation; no LF-noise source found",
        "tag": "DOCUMENTED, VERIFY"},
    "HDD_PINHEIRO2007": {
        "cite": "E. Pinheiro, W.-D. Weber, L.A. Barroso, 'Failure Trends in a Large Disk Drive "
                "Population', USENIX FAST 2007",
        "checked": "not searched this session; from prior knowledge. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "FLASH_SCHROEDER2016": {
        "cite": "B. Schroeder, R. Lagisetty, A. Merchant, 'Flash Reliability in Production: The "
                "Expected and the Unexpected', USENIX FAST 2016",
        "checked": "not searched this session; from prior knowledge. VERIFY",
        "tag": "DOCUMENTED, VERIFY"},
    "PD_IEC60270": {
        "cite": "IEC 60270, high-voltage test techniques: partial discharge measurements",
        "checked": "not searched this session; precursor reading is PROPOSED. VERIFY",
        "tag": "VERIFY"},
}

DEFAULTS = {
    "window": 1024,
    "step": None,              # None -> window (non-overlapping)
    "levels": (0.0, 0.5, 1.0, 2.0),
    "baseline_windows": 4,
    "rise_pct": 100.0,
    "persist": 3,
    "stability_tol": 0.5,      # max relative spread of h across levels to count as stable
    "floor_frac": 0.01,        # residual baseline floor = floor_frac * baseline white level
    "trend_windows": 5,
    "seed": 0,
}


# ---------------------------------------------------------------- numerics

def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def linfit(xs, ys):
    """Least-squares slope and intercept."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0)
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return 0.0, my
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return slope, my - slope * mx


def detrend(y):
    slope, icpt = linfit(list(range(len(y))), y)
    return [v - (slope * i + icpt) for i, v in enumerate(y)]


def allan_variance(y, m):
    """Non-overlapping Allan variance at block size m. Needs >= 2 blocks."""
    nb = len(y) // m
    if nb < 2:
        return None, 0
    bm = [sum(y[i * m:(i + 1) * m]) / m for i in range(nb)]
    return 0.5 * mean([(bm[i + 1] - bm[i]) ** 2 for i in range(nb - 1)]), nb


def scales_for(n, min_blocks=8):
    out, m = [], 1
    while n // m >= min_blocks:
        out.append(m)
        m *= 2
    return out


def solve3(A, b):
    """Gaussian elimination with partial pivoting for a 3x3 system."""
    M = [row[:] + [bv] for row, bv in zip(A, b)]
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-300:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(3):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, 4):
                    M[r][k] -= f * M[c][k]
    return [M[i][3] / M[i][i] for i in range(3)]


def fit_noise_model(y, scales):
    """Weighted LS fit of AV(m) = a/m + h + b*m. Weight ~ blocks / AV^2 (relative error).
    Returns dict(a, h, b, av)."""
    pts = []
    for m in scales:
        av, nb = allan_variance(y, m)
        if av is not None and av > 0:
            pts.append((m, av, nb))
    if len(pts) < 3:
        return None
    A = [[0.0] * 3 for _ in range(3)]
    rhs = [0.0] * 3
    for m, av, nb in pts:
        w = (nb - 1) / (av * av)
        f = (1.0 / m, 1.0, float(m))
        for i in range(3):
            rhs[i] += w * f[i] * av
            for j in range(3):
                A[i][j] += w * f[i] * f[j]
    sol = solve3(A, rhs)
    if sol is None:
        return None
    return {"a": sol[0], "h": sol[1], "b": sol[2], "av": {m: av for m, av, _ in pts}}


# ---------------------------------------------------------------- titration

def titrate_window(y, sigma_ref, levels, rng, stability_tol):
    """Inject known white noise at each level; read what moves and what holds."""
    yd = detrend(y)
    scales = scales_for(len(yd))
    fits = []
    for lv in levels:
        s = lv * sigma_ref
        yk = yd if s == 0 else [v + rng.gauss(0.0, s) for v in yd]
        f = fit_noise_model(yk, scales)
        if f is None:
            return None
        fits.append((s * s, f))
    a0, h0, b0 = fits[0][1]["a"], fits[0][1]["h"], fits[0][1]["b"]
    inj = [s2 for s2, _ in fits]
    recovery, _ = linfit(inj, [f["a"] - a0 for _, f in fits]) if max(inj) > 0 else (None, 0)
    hs = [f["h"] for _, f in fits]
    scale = max(abs(h0), 1e-30)
    spread = (max(hs) - min(hs)) / scale
    return {
        "white": a0,
        "residual": h0,
        "walk": b0,
        "residual_by_level": [round(h, 12) for h in hs],
        "injection_recovery": None if recovery is None else round(recovery, 4),
        "residual_spread": round(spread, 4),
        "stable": h0 > 0 and spread <= stability_tol,
    }


def analyze(readings, tolerance=None, tolerance_pct=None, nominal=None, **kw):
    """Titrate each window of `readings`; return a report dict.
    tolerance: absolute band around nominal; or tolerance_pct of nominal. nominal defaults
    to the mean of the baseline windows."""
    p = dict(DEFAULTS)
    p.update({k: v for k, v in kw.items() if v is not None})
    W = int(p["window"])
    step = int(p["step"] or W)
    levels = tuple(p["levels"])
    if levels[0] != 0.0:
        levels = (0.0,) + levels
    rng = random.Random(p["seed"])
    starts = list(range(0, len(readings) - W + 1, step))
    if len(starts) < p["baseline_windows"] + 1:
        return {"error": "series too short: need > baseline_windows windows",
                "n_readings": len(readings), "window": W}

    # sigma_ref from baseline windows, untitrated: sqrt(median white level)
    base_white = []
    for s0 in starts[:p["baseline_windows"]]:
        f = fit_noise_model(detrend(readings[s0:s0 + W]), scales_for(W))
        if f is not None:
            base_white.append(max(f["a"], 0.0))
    sigma_ref = math.sqrt(median(base_white)) if base_white else 0.0

    windows = []
    for s0 in starts:
        y = readings[s0:s0 + W]
        t = titrate_window(y, sigma_ref, levels, rng, p["stability_tol"])
        rec = {"start": s0, "tick": s0 + W - 1, "mean": mean(y)}
        if t is None:
            rec.update({"residual": None, "stable": False})
        else:
            rec.update(t)
        windows.append(rec)

    base = windows[:p["baseline_windows"]]
    if nominal is None:
        nominal = mean([w["mean"] for w in base])
    if tolerance is None and tolerance_pct is not None:
        tolerance = abs(nominal) * tolerance_pct / 100.0
    res_base = median([w["residual"] for w in base if w.get("residual") is not None])
    white_base = median([w["white"] for w in base if w.get("white") is not None])
    denom = max(res_base, p["floor_frac"] * white_base, 1e-30)

    run, first_flag, first_exit = 0, None, None
    hist = []
    for i, w in enumerate(windows):
        inside = tolerance is None or abs(w["mean"] - nominal) <= tolerance
        w["mean_inside_tolerance"] = inside
        if not inside and first_exit is None and i >= p["baseline_windows"]:
            first_exit = w["tick"]
        r = w.get("residual")
        w["residual_rise_pct"] = None if r is None else round((r - res_base) / denom * 100.0, 2)
        hist.append(r if r is not None else res_base)
        tw = hist[-p["trend_windows"]:]
        w["residual_trend"] = linfit(list(range(len(tw))), tw)[0] / denom if len(tw) > 1 else 0.0
        rising = (i >= p["baseline_windows"] and w["residual_rise_pct"] is not None
                  and w["residual_rise_pct"] >= p["rise_pct"] and w["stable"] and inside)
        run = run + 1 if rising else 0
        w["flag"] = run >= p["persist"]
        if w["flag"] and first_flag is None:
            first_flag = w["tick"]

    return {
        "status": "PROPOSED method; output is a reading, not a verdict",
        "params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items()},
        "n_readings": len(readings),
        "nominal": nominal,
        "tolerance": tolerance,
        "sigma_ref": sigma_ref,
        "baseline": {"residual": res_base, "white": white_base, "denominator": denom},
        "first_flag_tick": first_flag,
        "first_mean_exit_tick": first_exit,
        "lead_ticks": (first_exit - first_flag) if (first_flag is not None and first_exit is not None) else None,
        "windows": windows,
        "flag_meaning": "residual (1/f floor) up >= rise_pct for persist windows, titration-stable, "
                        "while window mean still inside tolerance",
    }


# ---------------------------------------------------------------- synthetic demo (ILLUSTRATIVE)

def pink_noise(n, rng, rows=16):
    """Voss-McCartney approximation of 1/f noise, scaled to ~unit variance."""
    vals = [rng.gauss(0, 1) for _ in range(rows)]
    total = sum(vals)
    out = []
    for i in range(n):
        if i:
            # update the row given by the number of trailing zeros of i
            k = (i & -i).bit_length() - 1
            if k < rows:
                total -= vals[k]
                vals[k] = rng.gauss(0, 1)
                total += vals[k]
        out.append((total + rng.gauss(0, 1)) / math.sqrt(rows + 1))
    return out


def synthetic(n=16384, nominal=100.0, white=0.05, flicker_start=0.01, flicker_end=0.01,
              drift_start_frac=0.6, drift_end=1.2, seed=1):
    """ILLUSTRATIVE readings: nominal + white + flicker(amplitude ramps) + late quadratic drift."""
    rng = random.Random(seed)
    pk = pink_noise(n, rng)
    out = []
    for i in range(n):
        f = i / (n - 1)
        amp = flicker_start + (flicker_end - flicker_start) * f
        d = 0.0
        if f > drift_start_frac:
            d = drift_end * ((f - drift_start_frac) / (1 - drift_start_frac)) ** 2
        out.append(nominal + d + amp * pk[i] + rng.gauss(0, white))
    return out


def demo(as_json=False):
    tol = 0.5  # 0.5 % of nominal 100.0
    healthy = synthetic(flicker_end=0.01, drift_end=0.0)
    failing = synthetic(flicker_end=0.25, drift_end=1.2)
    rh, rf = analyze(healthy, tolerance=tol), analyze(failing, tolerance=tol)
    if as_json:
        print(json.dumps({"healthy": rh, "failing": rf}, indent=2))
        return 0
    print("NOISE TITRATION DEMO -- ILLUSTRATIVE synthetic data, NOT field evidence")
    print("nominal 100.0, tolerance +/-%.2f, window %d, injection levels %s x sigma_ref"
          % (tol, DEFAULTS["window"], list(DEFAULTS["levels"])))
    print("healthy: constant small 1/f | failing: 1/f amplitude 0.01 -> 0.25, mean drift from 60% of run\n")
    print("%6s | %9s %9s %5s %4s | %9s %9s %5s %4s" % ("tick", "mean", "rise%", "stbl", "FLAG",
                                                    "mean", "rise%", "stbl", "FLAG"))
    print("%6s | %-30s | %-30s" % ("", "healthy", "failing"))
    for wh, wf in zip(rh["windows"], rf["windows"]):
        def cell(w):
            out = " " if w["mean_inside_tolerance"] else "!"
            return "%8.3f%s %9.1f %5s %4s" % (w["mean"], out, w["residual_rise_pct"] or 0.0,
                                               "y" if w["stable"] else "-", "<<" if w["flag"] else "")
        print("%6d | %s | %s" % (wh["tick"], cell(wh), cell(wf)))
    print("\n! = window mean outside tolerance")
    for name, r in (("healthy", rh), ("failing", rf)):
        print("%-8s first flag tick: %-6s first mean exit tick: %-6s lead: %s ticks"
              % (name, r["first_flag_tick"], r["first_mean_exit_tick"], r["lead_ticks"]))
    return 0


# ---------------------------------------------------------------- selftest

def selftest():
    rng = random.Random(3)
    checks = []
    # 1. Allan variance of white noise ~ sigma^2/m
    w = [rng.gauss(0, 1) for _ in range(65536)]
    av1, _ = allan_variance(w, 1)
    av16, _ = allan_variance(w, 16)
    checks.append(("white AV(1) ~ 1", abs(av1 - 1) < 0.05))
    checks.append(("white AV(16) ~ 1/16", abs(av16 * 16 - 1) < 0.15))
    # 2. fit separates white from flicker
    fw = fit_noise_model(w[:8192], scales_for(8192))
    pk = [0.3 * v + rng.gauss(0, 0.05) for v in pink_noise(8192, rng)]
    fp = fit_noise_model(pk, scales_for(8192))
    checks.append(("white-only: residual h / white a near 0", abs(fw["h"] / fw["a"]) < 0.01))
    checks.append(("pink: residual h / white a > 1", fp["h"] / fp["a"] > 1))
    # 3. titration: injection recovered in the white term, residual stable for pink
    t = titrate_window(pk[:2048], 0.05, (0, 0.5, 1, 2), random.Random(0), 0.5)
    checks.append(("injection recovery slope ~ 1", t["injection_recovery"] is not None
                   and 0.6 < t["injection_recovery"] < 1.4))
    checks.append(("pink residual titration-stable", t["stable"]))
    tw = titrate_window([rng.gauss(0, 1) for _ in range(2048)], 1.0, (0, 0.5, 1, 2), random.Random(0), 0.5)
    checks.append(("white-only residual not stable", not tw["stable"]))
    # 4. demo: flag fires before mean exits; healthy never flags
    tol = 0.5
    rh = analyze(synthetic(flicker_end=0.01, drift_end=0.0), tolerance=tol)
    rf = analyze(synthetic(flicker_end=0.25, drift_end=1.2), tolerance=tol)
    checks.append(("healthy: no flag", rh["first_flag_tick"] is None))
    checks.append(("healthy: mean never exits", rh["first_mean_exit_tick"] is None))
    checks.append(("failing: mean exits", rf["first_mean_exit_tick"] is not None))
    checks.append(("failing: flag before exit", rf["first_flag_tick"] is not None
                   and rf["first_flag_tick"] < rf["first_mean_exit_tick"]))
    # 5. healthy false-flag sweep over seeds
    ff = sum(analyze(synthetic(flicker_end=0.01, drift_end=0.0, seed=s), tolerance=tol)["first_flag_tick"]
             is not None for s in range(10, 30))
    checks.append(("healthy false flags <= 1/20 seeds (got %d)" % ff, ff <= 1))
    # 6. short series -> error, not a verdict
    checks.append(("short series reports error", "error" in analyze([1.0] * 100)))
    checks.append(("report json-serialisable", bool(json.dumps(rf))))
    bad = [n for n, ok in checks if not ok]
    print("noise_titration --selftest: %d/%d checks pass" % (len(checks) - len(bad), len(checks)))
    for n in bad:
        print("  FAIL:", n)
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Noise titration of one component's readings (PROPOSED).")
    ap.add_argument("readings", nargs="?", help="file: one reading per line")
    ap.add_argument("--tolerance", type=float, help="absolute band around nominal")
    ap.add_argument("--tolerance-pct", type=float, help="band as %% of nominal")
    ap.add_argument("--nominal", type=float, help="default: mean of baseline windows")
    ap.add_argument("--window", type=int)
    ap.add_argument("--rise-pct", type=float)
    ap.add_argument("--persist", type=int)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.demo:
        return demo(a.json)
    if not a.readings:
        ap.print_usage(sys.stderr)
        return 2
    try:
        with open(a.readings, encoding="utf-8") as fh:
            xs = [float(l) for l in fh if l.strip()]
    except (OSError, ValueError) as e:
        sys.stderr.write("cannot read readings: %s\n" % e)
        return 2
    rep = analyze(xs, tolerance=a.tolerance, tolerance_pct=a.tolerance_pct, nominal=a.nominal,
                  window=a.window, rise_pct=a.rise_pct, persist=a.persist)
    if a.json or "error" in rep:
        print(json.dumps(rep, indent=2))
        return 3 if "error" in rep else 0
    print("windows %d | first flag %s | first mean exit %s | lead %s"
          % (len(rep["windows"]), rep["first_flag_tick"], rep["first_mean_exit_tick"], rep["lead_ticks"]))
    for w in rep["windows"]:
        print("%7d mean %.6g rise %s%% stable %s %s" % (w["tick"], w["mean"], w["residual_rise_pct"],
                                                      w["stable"], "FLAG" if w["flag"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
