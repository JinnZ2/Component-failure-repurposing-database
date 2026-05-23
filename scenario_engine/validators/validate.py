"""validate_prediction: grade a single claim against a single actual_outcome.

Companion to `OutcomeChecker` (which works against the full ScenarioState
list). Used by `scenario_engine.runner.session.Session` after each tick.

Schema tolerance:
  * `actual` MAY be flat: `actual[name] = value` and `actual["system_state"]`
    (the SustainedDrift / interface-contract canonical form).
  * `actual` MAY be nested: `actual["measurements"][name] = value` (the form
    used by the 15 baseline scenarios).
Both are supported.
"""

from typing import Any, Dict

from ..claims.schema import CATEGORICAL_VALUES, _split_at_tick


def _lookup_measurement(name: str, actual: Dict[str, Any]):
    """Return (found, value). Tries flat first, then nested 'measurements'."""
    if name in actual and not isinstance(actual[name], (dict, list)):
        return True, actual[name]
    measurements = actual.get("measurements")
    if isinstance(measurements, dict) and name in measurements:
        return True, measurements[name]
    return False, None


def _lookup_category(name: str, actual: Dict[str, Any]):
    """Categoricals: 'system_state' lives at top level by convention. Allow
    flat-named categoricals at the top level too."""
    if name in actual and isinstance(actual[name], str):
        return True, actual[name]
    if name == "system_state":
        return True, actual.get("system_state", "unknown")
    return False, None


def validate_prediction(
    claim: Dict[str, Any],
    actual: Dict[str, Any],
) -> Dict[str, Any]:
    """Grade a claim against a single actual_outcome dict.

    Returns the validator-result dict that gets stored on the claim:

      {
        "claim_id": ...,
        "status": "VALIDATED" | "INVALIDATED" | "PARTIAL",
        "error_margins": {key: float, ...},
        "within_tolerance": bool,
        "targets_evaluated": int,
        "targets_matched": int,
        "notes": str,
      }
    """
    claim_id = claim.get("claim_id")
    pred = claim.get("prediction", {}) or {}
    tolerance = pred.get("tolerance", 0.0)
    try:
        tolerance = float(tolerance)
    except (TypeError, ValueError):
        tolerance = 0.0

    targets = []
    for k, v in pred.items():
        parsed = _split_at_tick(k)
        if parsed is None:
            continue
        base, _ = parsed
        targets.append((k, base, v))

    if not targets:
        return {
            "claim_id": claim_id,
            "status": "INVALIDATED",
            "error_margins": {},
            "within_tolerance": False,
            "targets_evaluated": 0,
            "targets_matched": 0,
            "notes": "no falsifiable target keys",
        }

    margins: Dict[str, float] = {}
    matched = 0
    notes = []

    for key, base, predicted in targets:
        if isinstance(predicted, str):
            if predicted not in CATEGORICAL_VALUES:
                margins[key] = float("inf")
                notes.append(f"{key}: unknown category {predicted!r}")
                continue
            found, actual_val = _lookup_category(base, actual)
            if not found:
                margins[key] = float("inf")
                notes.append(f"{key}: no categorical {base!r}")
                continue
            if actual_val == predicted:
                matched += 1
                margins[key] = 0.0
            else:
                margins[key] = 1.0
                notes.append(f"{key}: actual={actual_val!r}")
        elif isinstance(predicted, (int, float)) and not isinstance(predicted, bool):
            found, actual_val = _lookup_measurement(base, actual)
            if not found:
                margins[key] = float("inf")
                notes.append(f"{key}: no measurement {base!r}")
                continue
            try:
                err = abs(float(actual_val) - float(predicted))
            except (TypeError, ValueError):
                margins[key] = float("inf")
                notes.append(f"{key}: non-numeric actual={actual_val!r}")
                continue
            margins[key] = err
            if err <= tolerance:
                matched += 1
            else:
                notes.append(f"{key}: |{actual_val} - {predicted}| = {err:.4f} > tol {tolerance}")
        else:
            margins[key] = float("inf")
            notes.append(f"{key}: predicted has invalid type {type(predicted).__name__}")

    total = len(targets)
    if matched == total:
        status, within = "VALIDATED", True
    elif matched == 0:
        status, within = "INVALIDATED", False
    else:
        status, within = "PARTIAL", False

    return {
        "claim_id": claim_id,
        "status": status,
        "error_margins": margins,
        "within_tolerance": within,
        "targets_evaluated": total,
        "targets_matched": matched,
        "notes": "; ".join(notes),
    }
