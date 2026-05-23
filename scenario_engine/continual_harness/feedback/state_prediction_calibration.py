"""
scenario_engine.continual_harness.feedback.state_prediction_calibration

Calibrates categorical state predictions ("stable" / "degraded" / "failed")
against actual outcomes.

The numeric calibration we already have catches "AI predicts 38C but actual
is 47C." This module catches "AI predicts 'stable' but actual is 'degraded'."

Useful when:
  - Numeric prediction is correct but classification thresholds are off
  - AI assumes intervention fully resolves degradation but it only partially
    resolves it
  - State machine has hidden coupling (e.g. system still degraded because
    of a different component than the one the AI fixed)

Produces a confusion matrix and detects systematic mis-classifications.
"""

from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple


STATE_VALUES = ("stable", "degraded", "failed", "nominal")


def _parse_actual_from_notes(notes: str, key: str) -> Optional[str]:
    """Extract `actual=<value>` for a given prediction key out of the
    validator's free-form notes string. Returns None if not present.
    """
    if not notes:
        return None
    tag = f"{key}: actual="
    if tag not in notes:
        return None
    tail = notes.split(tag, 1)[1]
    end = tail.find(";")
    chunk = (tail[:end] if end >= 0 else tail).strip()
    return chunk.strip("'").strip('"')


def _extract_state_predictions(
    records: List[Dict[str, Any]],
) -> List[Tuple[str, str]]:
    """
    Returns list of (predicted_state, actual_state) tuples from validated
    claims that include a system_state prediction.

    Supports two schemas:
      - upstream:  errors[key] = "match" or "predicted=X actual=Y"
      - our store: error_margins[key] = float (0.0 match / 1.0 miss),
                   notes contains "key: actual='Y'" for misses
    """
    out = []
    for r in records:
        pred = r.get("prediction", {})
        val = r.get("validator") or r.get("validation")
        if not val:
            continue
        errors = val.get("error_margins") or val.get("errors") or {}
        notes = val.get("notes", "")
        for key, predicted in pred.items():
            if "system_state" not in key:
                continue
            if not isinstance(predicted, str):
                continue
            err_data = errors.get(key)

            # Upstream string schema
            if err_data == "match":
                out.append((predicted, predicted))
                continue
            if isinstance(err_data, str) and "actual=" in err_data:
                actual = err_data.split("actual=")[1].strip().strip("'").strip('"')
                out.append((predicted, actual))
                continue

            # Our numeric-margin schema
            if isinstance(err_data, (int, float)) and not isinstance(err_data, bool):
                if err_data == 0.0:
                    out.append((predicted, predicted))
                else:
                    actual = _parse_actual_from_notes(notes, key)
                    if actual is not None:
                        out.append((predicted, actual))
                continue
    return out


def confusion_matrix(
    records: List[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    """
    Build state prediction confusion matrix:
      matrix[predicted][actual] = count
    """
    pairs = _extract_state_predictions(records)
    matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for predicted, actual in pairs:
        matrix[predicted][actual] += 1
    # Flatten to plain dict for JSON serialization
    return {p: dict(actuals) for p, actuals in matrix.items()}


def state_accuracy(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Per-predicted-state accuracy:
      - When AI predicted "stable", how often was actual "stable"?
      - When AI predicted "degraded", how often was actual "degraded"?
    """
    matrix = confusion_matrix(records)
    out = {}
    for predicted, actuals in matrix.items():
        total = sum(actuals.values())
        correct = actuals.get(predicted, 0)
        out[predicted] = {
            "total_predictions": total,
            "correct": correct,
            "accuracy": correct / total if total else 0.0,
            "actuals_breakdown": actuals,
        }
    return out


def systematic_state_bias(
    records: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Detect systematic state mis-classification patterns.
    Returns each pattern with frequency.

    E.g.: "AI predicts 'stable' when actual is 'degraded' 80% of the time"
          suggests AI is too optimistic about intervention efficacy.
    """
    pairs = _extract_state_predictions(records)
    if not pairs:
        return None

    mispredictions = defaultdict(int)
    for predicted, actual in pairs:
        if predicted != actual:
            mispredictions[(predicted, actual)] += 1

    total_mispredict = sum(mispredictions.values())
    total = len(pairs)

    patterns = []
    for (pred, actual), count in sorted(
        mispredictions.items(), key=lambda x: x[1], reverse=True
    ):
        patterns.append({
            "predicted": pred,
            "actual": actual,
            "count": count,
            "ratio_of_mispredictions": (
                count / total_mispredict if total_mispredict else 0.0
            ),
            "ratio_of_all_predictions": count / total if total else 0.0,
        })

    # Most-common bias direction
    bias_direction = None
    if patterns:
        top = patterns[0]
        if top["ratio_of_mispredictions"] > 0.5:
            # Over half of all mispredictions are this single (pred, actual)
            bias_direction = (
                f"AI predicts '{top['predicted']}' "
                f"when actual is '{top['actual']}' "
                f"in {top['ratio_of_mispredictions']*100:.0f}% of errors"
            )

    return {
        "total_predictions": total,
        "total_mispredictions": total_mispredict,
        "overall_state_accuracy": 1.0 - (total_mispredict / total) if total else 0.0,
        "patterns": patterns,
        "bias_direction": bias_direction,
    }


def recommend_threshold_adjustment(
    bias: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    From a systematic_state_bias result, recommend a threshold adjustment
    direction.

    Logic:
      - If AI predicts 'stable' but actual 'degraded': intervention not
        as effective as assumed → require lower temp / longer recovery
        before declaring stable
      - If AI predicts 'degraded' but actual 'stable': AI too conservative;
        thresholds for 'stable' should be looser
      - If AI predicts 'stable' but actual 'failed': severe miscalibration;
        intervention insufficient
    """
    if not bias or not bias.get("patterns"):
        return None
    top = bias["patterns"][0]
    pred = top["predicted"]
    actual = top["actual"]

    recommendation = None
    if pred == "stable" and actual == "degraded":
        recommendation = {
            "action": "tighten_stable_threshold",
            "reasoning": (
                "AI declares 'stable' too aggressively. "
                "Either intervention is less effective than assumed, "
                "or coupled components are still degraded. "
                "Recommendation: only predict 'stable' if all "
                "sensors below 90% of degraded threshold."
            ),
            "direction": "more_conservative",
        }
    elif pred == "degraded" and actual == "stable":
        recommendation = {
            "action": "loosen_stable_threshold",
            "reasoning": (
                "AI is too pessimistic. Actual system recovers fully "
                "but AI predicts lingering degradation."
            ),
            "direction": "less_conservative",
        }
    elif pred == "stable" and actual == "failed":
        recommendation = {
            "action": "abort_assumption_of_recovery",
            "reasoning": (
                "AI assumes intervention prevents failure but it doesn't. "
                "Either wrong intervention or insufficient timing."
            ),
            "direction": "much_more_conservative",
        }
    elif pred == "degraded" and actual == "failed":
        recommendation = {
            "action": "extend_failure_horizon",
            "reasoning": (
                "AI sees degradation but underestimates cascade. "
                "Predictions should anticipate failure when degraded "
                "state persists with rising rate."
            ),
            "direction": "more_conservative",
        }
    return recommendation
