"""Validator for noise-precursor claims (scenario_engine/claims/noise_precursor.py).

STATUS: PROPOSED, co-authored (2026-10-31). CC0. stdlib only.

Input: a claim dict and a titration report from src/noise_titration.py analyze().
The validator does NOT trust the report's own flag: it recomputes the rise tick and
the mean-exit tick from the per-window records using the CLAIM's parameters.

Timing (conservative):
    rise_tick          end tick of the persist-th consecutive window with
                       residual_rise_pct >= X, titration-stable, mean inside tolerance
    mean_exit_tick     end tick of the first post-baseline window whose mean is outside
    earliest_exit_tick start tick of that window (the crossing may be anywhere inside it)
    lead_ticks         earliest_exit_tick - rise_tick          (lower bound)
    lead_ticks_upper   mean_exit_tick     - rise_tick          (upper bound)

    CONFIRMED     lead_ticks >= N
    INCONCLUSIVE  lead_ticks < N <= lead_ticks_upper   (window resolution)
    REFUTED       no rise before exit, or lead_ticks_upper < N

Validators never grade reasoning. A CONFIRMED on synthetic data is ILLUSTRATIVE,
not field evidence; `data_class` is carried into the verdict for that reason.
"""

from typing import Any, Dict, Optional


def _verdict(claim, outcome, notes, data_class, **extra):
    v = {
        "claim_id": claim.get("claim_id"),
        "outcome": outcome,
        "notes": notes,
        "data_class": data_class,
        "parameters": dict(claim.get("parameters", {})),
        "source_matrix_row": dict(claim.get("source_matrix_row", {})),
    }
    v.update(extra)
    if data_class == "synthetic":
        v["notes"] += " ILLUSTRATIVE: synthetic data, not field evidence."
    return v


def validate_noise_precursor(
    claim: Dict[str, Any],
    report: Dict[str, Any],
    data_class: str = "unspecified",
) -> Dict[str, Any]:
    """Grade one noise-precursor claim against one titration report.
    data_class: 'synthetic' | 'bench' | 'field' | 'unspecified'."""
    p = claim.get("parameters", {})
    if "error" in report:
        return _verdict(claim, "INCONCLUSIVE", "report error: %s" % report["error"], data_class)
    windows = report.get("windows") or []
    nb = int((report.get("params") or {}).get("baseline_windows", 4))
    if len(windows) <= nb:
        return _verdict(claim, "INCONCLUSIVE", "no windows after baseline", data_class)

    nominal = report.get("nominal")
    tol: Optional[float] = p.get("tolerance")
    if tol is None and p.get("tolerance_pct") is not None and nominal is not None:
        tol = abs(nominal) * float(p["tolerance_pct"]) / 100.0
    if tol is None or nominal is None:
        return _verdict(claim, "INCONCLUSIVE", "tolerance or nominal unresolved", data_class)

    def inside(w):
        return abs(w["mean"] - nominal) <= tol

    if not all(inside(w) for w in windows[:nb]):
        return _verdict(claim, "INCONCLUSIVE", "mean outside tolerance during baseline", data_class)

    exit_i = next((i for i in range(nb, len(windows)) if not inside(windows[i])), None)
    if exit_i is None:
        return _verdict(claim, "INCONCLUSIVE",
                        "mean never left tolerance: no failure-side event to compare", data_class)

    X = float(p["rise_pct"])
    N = int(p["lead_ticks"])
    persist = int(p.get("persist_windows", 3))
    run, rise_i = 0, None
    for i in range(nb, exit_i):
        w = windows[i]
        r = w.get("residual_rise_pct")
        ok = r is not None and r >= X and bool(w.get("stable"))
        run = run + 1 if ok else 0
        if run >= persist:
            rise_i = i
            break

    exit_tick = windows[exit_i]["tick"]
    earliest_exit = windows[exit_i]["start"]
    if rise_i is None:
        return _verdict(claim, "REFUTED",
                        "mean left tolerance with no sustained residual rise >= %g%% first" % X,
                        data_class, rise_tick=None, mean_exit_tick=exit_tick,
                        earliest_exit_tick=earliest_exit)
    rise_tick = windows[rise_i]["tick"]
    lead, lead_hi = earliest_exit - rise_tick, exit_tick - rise_tick
    common = dict(rise_tick=rise_tick, mean_exit_tick=exit_tick, earliest_exit_tick=earliest_exit,
                  lead_ticks=lead, lead_ticks_upper=lead_hi)
    if lead >= N:
        return _verdict(claim, "CONFIRMED",
                        "residual up >= %g%% %d ticks (lower bound) before mean exit; N = %d" % (X, lead, N),
                        data_class, **common)
    if lead_hi >= N:
        return _verdict(claim, "INCONCLUSIVE",
                        "lead %d..%d ticks straddles N = %d: within window resolution" % (lead, lead_hi, N),
                        data_class, **common)
    return _verdict(claim, "REFUTED", "lead %d..%d ticks < N = %d" % (lead, lead_hi, N),
                    data_class, **common)
