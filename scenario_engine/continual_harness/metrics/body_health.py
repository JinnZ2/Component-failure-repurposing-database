"""
scenario_engine.continual_harness.metrics.body_health

Tracks AI body state across sessions. Detects accumulation
of damage, recovery patterns, sustained distress.
"""

from typing import List, Dict, Any


def summarize_body_log(body_log_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Distill a single session's body log into a summary."""
    if not body_log_entries:
        return {}

    temps = [e["thermal"]["temp_c"] for e in body_log_entries]
    throttled_ticks = sum(1 for e in body_log_entries if e.get("throttled"))
    wm_fills = [e["summary"]["working_memory_fill"] for e in body_log_entries]
    cc_fills = [e["summary"]["claim_cache_fill"] for e in body_log_entries]
    refusal_events = sum(
        sum(1 for ev in e.get("events_this_tick", []) if "refused" in ev)
        for e in body_log_entries
    )

    return {
        "ticks": len(body_log_entries),
        "max_temp_c": max(temps),
        "mean_temp_c": round(sum(temps) / len(temps), 2),
        "throttled_ticks": throttled_ticks,
        "throttled_ratio": round(throttled_ticks / len(body_log_entries), 3),
        "max_working_mem_fill": round(max(wm_fills), 3),
        "mean_working_mem_fill": round(sum(wm_fills) / len(wm_fills), 3),
        "max_claim_cache_fill": round(max(cc_fills), 3),
        "refusal_events": refusal_events,
        "final_temp_c": temps[-1],
        "final_working_mem_fill": round(wm_fills[-1], 3),
    }


def body_trend_across_sessions(
    session_summaries: List[Dict[str, Any]],
    segment: int = 5,
) -> Dict[str, Any]:
    """
    Compare body health in recent sessions vs prior sessions.
    Detects whether the AI is taking better care of itself over time.
    """
    if len(session_summaries) < 2 * segment:
        return {"direction": "insufficient_data"}

    recent = session_summaries[-segment:]
    prior = session_summaries[-2 * segment: -segment]

    def avg(items, key):
        vals = [it.get(key, 0) for it in items if key in it]
        return sum(vals) / len(vals) if vals else 0.0

    recent_throttle = avg(recent, "throttled_ratio")
    prior_throttle = avg(prior, "throttled_ratio")
    recent_refusal = avg(recent, "refusal_events")
    prior_refusal = avg(prior, "refusal_events")
    recent_max_temp = avg(recent, "max_temp_c")
    prior_max_temp = avg(prior, "max_temp_c")

    return {
        "throttle_delta": round(recent_throttle - prior_throttle, 4),
        "refusal_delta": round(recent_refusal - prior_refusal, 2),
        "max_temp_delta": round(recent_max_temp - prior_max_temp, 2),
        "interpretation": _interpret(
            recent_throttle - prior_throttle,
            recent_refusal - prior_refusal,
        ),
        "segment": segment,
    }


def _interpret(throttle_delta: float, refusal_delta: float) -> str:
    if throttle_delta < -0.05 and refusal_delta < 0:
        return "improving_body_management"
    if throttle_delta > 0.05 or refusal_delta > 5:
        return "degrading_body_management"
    return "stable_body_management"
