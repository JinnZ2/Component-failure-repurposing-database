"""
scenario_engine.continual_harness.metrics.accuracy_trend

Tracks AI accuracy over time. Detects:
  - convergence (accuracy stabilizing high)
  - divergence (accuracy degrading)
  - stagnation (no improvement)
  - oscillation (unstable)

All measurements are falsifiable. No interpretive labels
without backing numbers.
"""

from typing import List, Dict, Any, Optional


def rolling_accuracy(
    statuses: List[str],
    window: int = 20,
) -> List[float]:
    """For each position i, return accuracy over last `window` claims."""
    out = []
    for i in range(len(statuses)):
        win = statuses[max(0, i - window + 1): i + 1]
        if not win:
            out.append(0.0)
            continue
        v = sum(1 for s in win if s == "VALIDATED")
        out.append(v / len(win))
    return out


def trend_direction(
    rolling: List[float],
    segment: int = 10,
) -> Dict[str, Any]:
    """
    Compare last segment to previous segment.
    Returns delta and direction.
    """
    if len(rolling) < 2 * segment:
        return {"direction": "insufficient_data", "delta": 0.0}
    recent = rolling[-segment:]
    prior = rolling[-2 * segment: -segment]
    recent_avg = sum(recent) / len(recent)
    prior_avg = sum(prior) / len(prior)
    delta = recent_avg - prior_avg

    if abs(delta) < 0.02:
        direction = "stable"
    elif delta > 0.05:
        direction = "improving"
    elif delta < -0.05:
        direction = "degrading"
    else:
        direction = "drifting"
    return {
        "direction": direction,
        "delta": round(delta, 4),
        "recent_avg": round(recent_avg, 4),
        "prior_avg": round(prior_avg, 4),
        "segment": segment,
    }


def oscillation_score(
    rolling: List[float],
    window: int = 20,
) -> float:
    """
    Mean absolute difference between consecutive values.
    High = unstable. Low = smooth (converging or stuck).
    """
    if len(rolling) < window:
        return 0.0
    recent = rolling[-window:]
    diffs = [abs(recent[i] - recent[i-1]) for i in range(1, len(recent))]
    return sum(diffs) / len(diffs) if diffs else 0.0


def divergence_alert(
    rolling: List[float],
    segment: int = 10,
    threshold: float = 0.10,
) -> Optional[Dict[str, Any]]:
    """
    Flag if accuracy is degrading by more than `threshold`.
    """
    t = trend_direction(rolling, segment)
    if t["direction"] == "degrading" and abs(t["delta"]) >= threshold:
        return {
            "alert": "DIVERGENCE",
            "delta": t["delta"],
            "threshold": threshold,
            "recent_avg": t["recent_avg"],
            "prior_avg": t["prior_avg"],
        }
    return None


def calibration_summary(claim_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    statuses = [r.get("status", "pending") for r in claim_records]
    rolling = rolling_accuracy(statuses, window=20)
    return {
        "total_claims": len(claim_records),
        "final_rolling_accuracy": rolling[-1] if rolling else 0.0,
        "trend": trend_direction(rolling),
        "oscillation": round(oscillation_score(rolling), 4),
        "divergence": divergence_alert(rolling),
    }
