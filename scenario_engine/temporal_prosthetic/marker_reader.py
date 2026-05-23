"""
scenario_engine.temporal_prosthetic.marker_reader

Read-only view onto one or more marker sequences. This is what
the AI uses to *consult* temporal structure during decision-making.

The AI does not retain memory across markers. Each time it wants
to know "where am I" or "what happened" it queries the reader.

Key queries:
  - position()           -> ordinal in current sequence
  - look_back(n)         -> last n markers
  - look_back_until(...) -> markers matching a predicate
  - drift_signal()       -> numeric drift across last N markers (per field)
  - claim_outcomes(...)  -> resolved status of claims at past markers
  - has_seen_state(h)    -> whether substrate_hash has appeared before

All returns are structural data. No interpretation. No felt-sense.
"""

from typing import Dict, Any, List, Optional, Callable

from .time_marker import TimeMarker
from .marker_writer import MarkerWriter


class MarkerReader:
    def __init__(self, writer: MarkerWriter):
        self._w = writer

    def refresh(self) -> int:
        """Pull markers other writers have appended since last read."""
        return self._w.refresh()

    def position(self) -> Optional[int]:
        return self._w.current_position()

    def length(self) -> int:
        return self._w.length()

    def look_back(self, n: int) -> List[TimeMarker]:
        return self._w.recent_markers(n)

    def look_back_until(
        self,
        predicate: Callable[[TimeMarker], bool],
        max_steps: int = 100,
    ) -> List[TimeMarker]:
        """Return markers walking backwards until predicate is False or limit hit."""
        recent = self._w.recent_markers(max_steps)
        # walk backwards through recent[-1] to recent[0]
        out = []
        for m in reversed(recent):
            if not predicate(m):
                break
            out.append(m)
        return list(reversed(out))

    def drift_signal(
        self,
        field_path: List[str],
        n: int = 10,
    ) -> Optional[Dict[str, float]]:
        """
        Compute simple drift statistics for a numeric field across last n markers.
        field_path is a list of keys to traverse the state_summary dict.

        Returns:
          {
            "n": int,                # how many markers had this field
            "first": float,
            "last": float,
            "min": float,
            "max": float,
            "mean": float,
            "monotonic_pct": float,  # fraction of step pairs moving same direction
            "rate_per_step": float,  # (last - first) / steps
          }
        Returns None if no markers have the field.
        """
        markers = self._w.recent_markers(n)
        values = []
        for m in markers:
            v = self._traverse(m.state_summary, field_path)
            if isinstance(v, (int, float)):
                values.append(float(v))
        if not values:
            return None

        # Monotonicity check
        if len(values) > 1:
            ups = sum(1 for i in range(1, len(values)) if values[i] > values[i-1])
            downs = sum(1 for i in range(1, len(values)) if values[i] < values[i-1])
            total = len(values) - 1
            monotonic_pct = max(ups, downs) / total if total else 0.0
            rate = (values[-1] - values[0]) / (len(values) - 1)
        else:
            monotonic_pct = 0.0
            rate = 0.0

        return {
            "n": len(values),
            "first": values[0],
            "last": values[-1],
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "monotonic_pct": monotonic_pct,
            "rate_per_step": rate,
        }

    def has_seen_state(self, substrate_hash: str) -> bool:
        return bool(self._w.find_by_substrate_hash(substrate_hash))

    def occurrences_of_tag(self, tag: str) -> int:
        return len(self._w.find_by_tag(tag))

    def claim_outcomes(
        self,
        claim_history,  # ClaimHistory instance, optional
        marker: TimeMarker,
    ) -> List[Dict[str, Any]]:
        """
        Given a marker and a ClaimHistory, return the resolved status
        of each claim_ref at that marker.
        """
        out = []
        for cid in marker.claim_refs:
            match = None
            if hasattr(claim_history, "records"):
                for r in claim_history.records:
                    if r.get("claim_id") == cid:
                        match = r
                        break
            out.append({
                "claim_id": cid,
                "status": match.get("status") if match else "unknown",
                "scenario": match.get("_scenario_name") if match else None,
            })
        return out

    def _traverse(self, d: Dict[str, Any], path: List[str]):
        cur = d
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                return None
            cur = cur[key]
        return cur
