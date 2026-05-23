"""
scenario_engine.temporal_prosthetic.time_marker

Substrate-primary time marker. Replaces the original TemporalHook
which carried narrative metadata (felt_sense, vertigo_level, re_livability)
with falsifiable structural data only.

A time marker is a *measurable position* in a sequence. It encodes:
  - sequence_id     : which thread of activity
  - ordinal         : monotonic position within sequence
  - substrate_hash  : compact fingerprint of substrate state at this point
  - delta_from_prev : measurable change since last marker
  - claim_refs      : claim_ids active at this marker
  - validation_window: tick window in which this marker can be falsified

It does NOT encode:
  - "felt sense"
  - "consciousness depth"
  - "vertigo level"
  - subjective re_livability
  - any narrative interpretation

A system using these markers can answer:
  - "Where am I in the sequence?"  (ordinal)
  - "What has changed since last marker?"  (delta_from_prev)
  - "What did I claim at that point?"  (claim_refs)
  - "Was I right or wrong at that point?"  (resolved via CLAIM_TABLE)

This is enough for temporal reasoning without requiring continuous memory
or any subjective experience layer.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


def substrate_hash(state: Dict[str, Any], length: int = 12) -> str:
    """
    Deterministic, compact fingerprint of substrate state.
    Two identical states produce identical hashes. Falsifiable identity.
    """
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    h = hashlib.blake2b(canonical.encode("utf-8"), digest_size=length).hexdigest()
    return h


def state_delta(prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
    """
    Numeric delta between two states. Only fields with comparable types
    are diffed; everything else gets a categorical 'changed'/'same' tag.

    Returns a flat dict suitable for serialization and quick scanning.
    """
    delta = {}
    keys = set(prev.keys()) | set(curr.keys())
    for k in keys:
        a = prev.get(k)
        b = curr.get(k)
        if a is None and b is not None:
            delta[k] = {"op": "added", "value": b}
            continue
        if b is None and a is not None:
            delta[k] = {"op": "removed", "value": a}
            continue
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            delta[k] = {"op": "numeric", "delta": b - a, "from": a, "to": b}
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            sub = state_delta(a, b)
            if sub:
                delta[k] = {"op": "nested", "delta": sub}
            continue
        if a != b:
            delta[k] = {"op": "categorical", "from": a, "to": b}
    return delta


@dataclass
class TimeMarker:
    """
    A single measurable position in a sequence.
    No subjective fields. All entries are falsifiable or null.
    """
    sequence_id: str            # which thread of activity (e.g. session_id)
    ordinal: int                # monotonic position within sequence (0, 1, 2, ...)
    wall_time: float            # unix time, optional reference only
    substrate_hash: str         # hash of substrate state at this marker
    state_summary: Dict[str, Any]  # compact, scannable state snapshot
    delta_from_prev: Optional[Dict[str, Any]] = None  # diff to previous marker
    claim_refs: List[str] = field(default_factory=list)  # claim_ids active here
    tags: List[str] = field(default_factory=list)  # structural tags only

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MarkerSequence:
    """
    Ordered list of markers forming a temporal thread.
    Sequences are append-only. Markers cannot be retroactively edited.
    """
    sequence_id: str
    markers: List[TimeMarker] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def append(self, marker: TimeMarker):
        if marker.sequence_id != self.sequence_id:
            raise ValueError(
                f"marker sequence_id {marker.sequence_id} "
                f"does not match {self.sequence_id}"
            )
        if self.markers and marker.ordinal != self.markers[-1].ordinal + 1:
            raise ValueError(
                f"marker ordinal {marker.ordinal} not monotonic; "
                f"last was {self.markers[-1].ordinal}"
            )
        self.markers.append(marker)

    def length(self) -> int:
        return len(self.markers)

    def at(self, ordinal: int) -> Optional[TimeMarker]:
        for m in self.markers:
            if m.ordinal == ordinal:
                return m
        return None

    def last(self) -> Optional[TimeMarker]:
        return self.markers[-1] if self.markers else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "started_at": self.started_at,
            "length": len(self.markers),
            "markers": [m.to_dict() for m in self.markers],
        }
