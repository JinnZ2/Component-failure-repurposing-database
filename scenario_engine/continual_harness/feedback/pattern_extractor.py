"""
scenario_engine.continual_harness.feedback.pattern_extractor

Reads ClaimHistory across many sessions and detects systematic
patterns the AI itself is not seeing.

This is the corrective signal layer. The AI makes claims; physics
falsifies them; the pattern extractor finds the structure in *which*
claims fail, *when*, and *under what conditions*.

Outputs are themselves falsifiable observations, written as a
structured PATTERN_TABLE.json that can be cross-validated.

No interpretation. Just structural facts about the claim record.
"""

import json
import os
from collections import defaultdict, Counter
from typing import Dict, Any, List, Optional, Tuple
from statistics import mean, stdev


def _numeric_error(claim: Dict[str, Any]) -> Optional[float]:
    """Extract worst numeric error from validation if any.

    Only counts margins for predictions whose VALUE was numeric in the
    claim's prediction dict; categorical predictions (e.g.
    'system_state_at_tick_N': 'stable') store their match outcome as
    0.0 / 1.0 in error_margins but are not numeric errors.
    """
    val = claim.get("validator") or claim.get("validation")
    if not val:
        return None
    errors = val.get("error_margins") or val.get("errors") or {}
    pred = claim.get("prediction", {})
    nums = []
    for k, v in errors.items():
        if not isinstance(v, (int, float)):
            continue
        predicted = pred.get(k)
        if isinstance(predicted, (int, float)) and not isinstance(predicted, bool):
            nums.append(v)
    return max(nums) if nums else None


def by_scenario_accuracy(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out = {}
    by_s = defaultdict(list)
    for r in records:
        s = r.get("_scenario_name") or "unknown"
        by_s[s].append(r)
    for s, rs in by_s.items():
        total = len(rs)
        v = sum(1 for r in rs if r.get("status") == "VALIDATED")
        i = sum(1 for r in rs if r.get("status") == "INVALIDATED")
        p = sum(1 for r in rs if r.get("status") == "PARTIAL")
        out[s] = {
            "total": total,
            "validated": v,
            "invalidated": i,
            "partial": p,
            "accuracy": v / total if total else 0.0,
        }
    return out


def by_decision_accuracy(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Which interventions tend to validate? Which tend to fail?"""
    by_d = defaultdict(list)
    for r in records:
        d = r.get("decision") or "no_decision"
        by_d[d].append(r)
    out = {}
    for d, rs in by_d.items():
        total = len(rs)
        v = sum(1 for r in rs if r.get("status") == "VALIDATED")
        out[d] = {
            "total": total,
            "validated": v,
            "accuracy": v / total if total else 0.0,
        }
    return out


def numeric_error_distribution(
    records: List[Dict[str, Any]],
) -> Optional[Dict[str, float]]:
    """Distribution of numeric errors across all claims."""
    errs = [_numeric_error(r) for r in records]
    errs = [e for e in errs if e is not None]
    if not errs:
        return None
    return {
        "n": len(errs),
        "min": min(errs),
        "max": max(errs),
        "mean": mean(errs),
        "stdev": stdev(errs) if len(errs) > 1 else 0.0,
    }


def systematic_bias(
    records: List[Dict[str, Any]],
    field_suffix: str = "_temp_c",
) -> Optional[Dict[str, Any]]:
    """
    For predictions of a given field type, are errors signed in one direction?
    A consistent positive or negative error indicates systematic bias.
    """
    signed_errors = []
    for r in records:
        val = r.get("validator") or r.get("validation")
        if not val:
            continue
        pred = r.get("prediction", {})
        errors = val.get("error_margins") or val.get("errors") or {}
        for key, err_val in errors.items():
            if field_suffix not in key:
                continue
            if not isinstance(err_val, (int, float)):
                continue
            # Find the predicted value for this key
            predicted = pred.get(key)
            if not isinstance(predicted, (int, float)):
                continue
            # err_val is abs(predicted - actual). We need sign.
            # Reconstruct sign from stored "from"/"to" if available.
            # Here we just record magnitude; bias detection uses count of
            # high-error claims.
            signed_errors.append({"key": key, "err": err_val, "predicted": predicted})

    if not signed_errors:
        return None
    high_err_count = sum(1 for e in signed_errors if e["err"] > 5.0)
    return {
        "field_suffix": field_suffix,
        "samples": len(signed_errors),
        "mean_error": mean(e["err"] for e in signed_errors),
        "high_error_count": high_err_count,
        "high_error_ratio": high_err_count / len(signed_errors),
    }


def recurring_failure_pattern(
    records: List[Dict[str, Any]],
    min_occurrences: int = 3,
) -> List[Dict[str, Any]]:
    """
    Find (scenario, decision) pairs that fail repeatedly.
    The AI keeps picking the same intervention and it keeps not working.
    """
    pairs = Counter()
    fails = Counter()
    for r in records:
        s = r.get("_scenario_name") or "unknown"
        d = r.get("decision") or "no_decision"
        pairs[(s, d)] += 1
        if r.get("status") == "INVALIDATED":
            fails[(s, d)] += 1

    out = []
    for (s, d), n in pairs.items():
        f = fails.get((s, d), 0)
        if n >= min_occurrences and f >= min_occurrences:
            out.append({
                "scenario": s,
                "decision": d,
                "attempts": n,
                "failures": f,
                "failure_rate": f / n,
            })
    out.sort(key=lambda x: x["failure_rate"], reverse=True)
    return out


def db_effectiveness_audit(
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    For claims with db_evidence, compare DB-claimed effectiveness
    against actual validation rate. If a DB intervention is rated
    High (0.9) but validates only 60% of the time, that's a
    measurable mismatch worth flagging.
    """
    by_intervention = defaultdict(list)
    for r in records:
        ev = r.get("db_evidence")
        if not ev:
            continue
        key = (ev.get("intervention"), ev.get("effectiveness_score"))
        by_intervention[key].append(r)

    out = []
    for (intervention, db_score), rs in by_intervention.items():
        if intervention is None:
            continue
        total = len(rs)
        v = sum(1 for r in rs if r.get("status") == "VALIDATED")
        observed_rate = v / total if total else 0.0
        out.append({
            "intervention": intervention,
            "db_effectiveness_score": db_score,
            "observed_validation_rate": observed_rate,
            "delta": observed_rate - (db_score or 0.0),
            "samples": total,
        })
    return out


def signed_numeric_errors(
    records: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Reconstruct signed errors: predicted - actual.
    The validation only stores abs(error), but we can compute the sign
    by re-deriving from claim.prediction and validation context.

    For now, since we don't store actual outcomes in the claim, we
    estimate sign by checking if the predicted value was below or
    above the predicted nominal range. A more robust version would
    store actual values in the validation record.

    Returns: {predicted_high_count, predicted_low_count, mean_abs}
    """
    over = 0  # predicted value higher than actual
    under = 0  # predicted value lower than actual
    samples = 0
    for r in records:
        pred = r.get("prediction", {})
        val = r.get("validator") or r.get("validation")
        if not val:
            continue
        errors = val.get("error_margins") or val.get("errors") or {}
        for k, predicted in pred.items():
            if not isinstance(predicted, (int, float)):
                continue
            err = errors.get(k)
            if not isinstance(err, (int, float)):
                continue
            samples += 1
            # Heuristic: if prediction was near nominal (low value for temp),
            # AI predicted aggressive cooling. If prediction was high, AI
            # predicted little cooling. We don't have actual here without
            # more info. Just count occurrences for now.
    return {"samples": samples}


def signed_bias_from_outcomes(
    records: List[Dict[str, Any]],
    state_logs_by_session: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Compute signed bias if state logs are available.
    For each claim with a numeric prediction, look up the actual outcome
    at the predicted tick in the state log, and compute predicted - actual.
    """
    if not state_logs_by_session:
        return None

    signed_per_field = {}
    for r in records:
        sid = r.get("_session_id")
        if not sid or sid not in state_logs_by_session:
            continue
        log = state_logs_by_session[sid]
        pred = r.get("prediction", {})
        for k, predicted in pred.items():
            if not isinstance(predicted, (int, float)):
                continue
            if "_at_tick_" not in k:
                continue
            base_key, target_tick_str = k.split("_at_tick_")
            try:
                target_tick = int(target_tick_str)
            except ValueError:
                continue
            # Find the state log entry for target_tick
            entry = next((e for e in log if e.get("tick") == target_tick), None)
            if not entry:
                continue
            actual = entry.get("actual_outcome", {}).get(base_key)
            if not isinstance(actual, (int, float)):
                continue
            signed_err = predicted - actual
            signed_per_field.setdefault(base_key, []).append(signed_err)

    if not signed_per_field:
        return None
    return {
        field: {
            "n": len(errs),
            "mean_signed": sum(errs) / len(errs),
            "mean_abs": sum(abs(e) for e in errs) / len(errs),
            "all_overpredict": all(e > 0 for e in errs),
            "all_underpredict": all(e < 0 for e in errs),
        }
        for field, errs in signed_per_field.items()
    }


def extract_all_patterns(
    history_path: str,
    output_path: Optional[str] = None,
    state_logs_by_session: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Read a ClaimHistory JSON file and return all detected patterns.
    Optionally write to PATTERN_TABLE.json.
    """
    if not os.path.exists(history_path):
        return {"error": f"history not found: {history_path}"}
    with open(history_path) as f:
        records = json.load(f)

    report = {
        "total_claims": len(records),
        "by_scenario": by_scenario_accuracy(records),
        "by_decision": by_decision_accuracy(records),
        "numeric_error_distribution": numeric_error_distribution(records),
        "systematic_bias_temp_c": systematic_bias(records, "_temp_c"),
        "signed_bias": signed_bias_from_outcomes(records, state_logs_by_session),
        "recurring_failures": recurring_failure_pattern(records),
        "db_effectiveness_audit": db_effectiveness_audit(records),
    }

    if output_path:
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

    return report
