"""Noise-precursor claim: residual noise rises before the mean drifts out of tolerance.

STATUS: PROPOSED claim, co-authored (2026-10-31). CC0. stdlib only.

Statement (parameters explicit, all required):
    "Residual noise rises by at least X% at least N ticks before mean drift
     exceeds tolerance."

    X  rise_pct        residual (1/f floor from noise titration) vs baseline, percent
    N  lead_ticks      minimum lead, in readings (ticks)
    tolerance          absolute band around nominal, OR tolerance_pct of nominal
    persist_windows    consecutive titration-stable windows needed to count the rise

Outcome vocabulary (its own; not mapped onto VALIDATED/INVALIDATED/PARTIAL used by
the per-tick claims in CLAIM_TABLE.substrate.json):
    CONFIRMED     sustained rise >= X%, and conservative lead >= N ticks
    REFUTED       mean left tolerance with no sustained rise first, or lead < N
    INCONCLUSIVE  no failure-side event (mean never left tolerance), mean out of
                  tolerance during baseline, series too short, or the lead is
                  below N only within window resolution

Provenance: every claim carries `source_matrix_row`, the locator format used by
component_db_adapter (matrix + row_index + identity keys), extended with the
row's "Pre-failure noise signature" and its status tag.

Published basis vs this claim: the matrix row's source (e.g. GAN_LED_2005,
VANDAMME1994, keys in src/noise_titration.py NOISE_SOURCES) reports noise changing
before DC parameters. The specific X, N and tolerance are ILLUSTRATIVE choices,
not values from any source.
"""

import json
import os
from typing import Any, Dict, Optional

from .schema import ClaimRejected
from ..component_db_adapter.csv_loader import load_csv

OUTCOMES = ("CONFIRMED", "REFUTED", "INCONCLUSIVE")
STATEMENT = ("Residual noise rises by at least {rise_pct:g}% at least {lead_ticks} ticks "
             "before mean drift exceeds tolerance ({tol}).")
CLAIMS_FILE = os.path.join(os.path.dirname(__file__), "NOISE_PRECURSOR_CLAIMS.json")
SIGNATURE_KEY = "pre-failure_noise_signature"
STATUS_KEY = "noise_signature_status"


def locate_noise_row(matrices_dir: str, component: str, failure_mode: str) -> Dict[str, Any]:
    """First failure_mode_matrix row for (component, failure_mode), as a locator."""
    rows = load_csv(os.path.join(matrices_dir, "failure_mode_matrix.csv"),
                    matrix_name="failure_mode_matrix")
    for r in rows:
        if r.get("component") == component and r.get("failure_mode") == failure_mode:
            return {
                "matrix": r["_matrix"],
                "row_index": r["_row_index"],
                "component": component,
                "failure_mode": failure_mode,
                "pre_failure_noise_signature": r.get(SIGNATURE_KEY, ""),
                "noise_signature_status": r.get(STATUS_KEY, ""),
            }
    raise KeyError("no failure_mode_matrix row for %r / %r" % (component, failure_mode))


def build_noise_precursor_claim(
    claim_id: str,
    rise_pct: float,
    lead_ticks: int,
    source_matrix_row: Dict[str, Any],
    tolerance: Optional[float] = None,
    tolerance_pct: Optional[float] = None,
    persist_windows: int = 3,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build and check a noise-precursor claim. Raises ClaimRejected if any
    parameter that makes it falsifiable is missing or out of range."""
    if not claim_id or not isinstance(claim_id, str):
        raise ClaimRejected("claim_id missing")
    if not isinstance(rise_pct, (int, float)) or isinstance(rise_pct, bool) or rise_pct <= 0:
        raise ClaimRejected("rise_pct (X) must be a positive number")
    if not isinstance(lead_ticks, int) or isinstance(lead_ticks, bool) or lead_ticks < 0:
        raise ClaimRejected("lead_ticks (N) must be a non-negative int")
    if (tolerance is None) == (tolerance_pct is None):
        raise ClaimRejected("give exactly one of tolerance / tolerance_pct")
    tol_val = tolerance if tolerance is not None else tolerance_pct
    if not isinstance(tol_val, (int, float)) or tol_val <= 0:
        raise ClaimRejected("tolerance must be positive")
    if not isinstance(persist_windows, int) or persist_windows < 1:
        raise ClaimRejected("persist_windows must be an int >= 1")
    if not (isinstance(source_matrix_row, dict) and source_matrix_row.get("matrix")
            and source_matrix_row.get("row_index")):
        raise ClaimRejected("source_matrix_row with matrix and row_index is required")
    tol_txt = ("+/-%g absolute" % tolerance) if tolerance is not None else ("+/-%g%% of nominal" % tolerance_pct)
    return {
        "claim_id": claim_id,
        "claim_type": "noise_precursor",
        "statement": STATEMENT.format(rise_pct=rise_pct, lead_ticks=lead_ticks, tol=tol_txt),
        "parameters": {
            "rise_pct": float(rise_pct),
            "lead_ticks": lead_ticks,
            "tolerance": tolerance,
            "tolerance_pct": tolerance_pct,
            "persist_windows": persist_windows,
        },
        "outcome_vocabulary": list(OUTCOMES),
        "source_matrix_row": dict(source_matrix_row),
        "provenance": dict(provenance or {}),
        "falsifiable": True,
        "status": "pending",
        "validator": {},
    }


def load_noise_precursor_claims(path: str = CLAIMS_FILE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["claims"]
