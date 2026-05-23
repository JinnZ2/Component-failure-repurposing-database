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

Field-name compatibility note: claims stored by Session use
  claim["validator"]["error_margins"] (numeric margins) and a
  claim["validator"]["notes"] string with actual=X for failed
  categorical predictions. Earlier upstream specs used
  claim["validation"]["errors"]. Every reader below tolerates both
  layouts so spec text and live claim files both flow through.
"""

import json
import os
from collections import defaultdict, Counter
from typing import Dict, Any, List, Optional, Tuple
from statistics import mean, stdev


def _validator_block(claim: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return claim.get("validator") or claim.get("validation")


def _errors_block(val: Dict[str, Any]) -> Dict[str, Any]:
    return val.get("error_margins") or val.get("errors") or {}


def _numeric_error(claim: Dict[str, Any]) -> Optional[float]:
    """Extract worst numeric error from validation if any.

    Only counts margins for predictions whose VALUE was numeric in the
    claim's prediction dict; categorical predictions (e.g.
    'system_state_at_tick_N': 'stable') store their match outcome as
    0.0 / 1.0 in error_margins but are not numeric errors.
    """
    val = _validator_block(claim)
    if not val:
        return None
    errors = _errors_block(val)
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
        val = _validator_block(r)
        if not val:
            continue
        pred = r.get("prediction", {})
        errors = _errors_block(val)
        for key, err_val in errors.items():
            if field_suffix not in key:
                continue
            if not isinstance(err_val, (int, float)):
                continue
            # Find the predicted value for this key
            predicted = pred.get(key)
            if not isinstance(predicted, (int, float)):
                continue
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
    against actual validation rate.
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
    from .state_prediction_calibration import (
        confusion_matrix,
        state_accuracy,
        systematic_state_bias,
        recommend_threshold_adjustment,
    )

    if not os.path.exists(history_path):
        return {"error": f"history not found: {history_path}"}
    with open(history_path) as f:
        records = json.load(f)

    state_bias = systematic_state_bias(records)
    state_recommendation = (
        recommend_threshold_adjustment(state_bias) if state_bias else None
    )

    report = {
        "total_claims": len(records),
        "by_scenario": by_scenario_accuracy(records),
        "by_decision": by_decision_accuracy(records),
        "numeric_error_distribution": numeric_error_distribution(records),
        "systematic_bias_temp_c": systematic_bias(records, "_temp_c"),
        "signed_bias": signed_bias_from_outcomes(records, state_logs_by_session),
        "recurring_failures": recurring_failure_pattern(records),
        "db_effectiveness_audit": db_effectiveness_audit(records),
        "state_prediction_confusion": confusion_matrix(records),
        "state_prediction_accuracy": state_accuracy(records),
        "state_prediction_bias": state_bias,
        "state_threshold_recommendation": state_recommendation,
    }

    if output_path:
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

    return report
