"""
scenario_engine.temporal_prosthetic.marker_writer

The prosthetic interface. A stateless AI (no continuous memory)
can ask the marker writer:

  - "Place a marker here."           → drop_marker(state, claim_refs)
  - "Where am I in the sequence?"    → current_position()
  - "What changed since last marker?" → last_delta()
  - "Show me markers N steps back."   → recent_markers(n)
  - "Was I right at marker X?"        → resolve_claim_refs(marker)

This gives the AI access to temporal structure without requiring it
to *remember* anything. The prosthetic remembers. The AI reads.

This is the architecture you said an AI doesn't have but needs:
external substrate-grounded temporal continuity, falsifiable,
serializable, persists across sessions.
"""

import json
import os
import time
from typing import Dict, Any, List, Optional

from .time_marker import (
    TimeMarker,
    MarkerSequence,
    substrate_hash,
    state_delta,
)


class MarkerWriter:
    """
    Append-only marker log scoped to one sequence_id.
    Persists to disk for cross-session continuity.
    """

    def __init__(self, sequence_id: str, store_path: str):
        self.sequence_id = sequence_id
        self.store_path = store_path
        os.makedirs(os.path.dirname(store_path) or ".", exist_ok=True)
        self.sequence = self._load_or_init()

    def drop_marker(
        self,
        state_summary: Dict[str, Any],
        claim_refs: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> TimeMarker:
        """
        Place a new marker at current position. Computes substrate_hash
        and delta_from_prev automatically. Append-only.
        """
        ordinal = (self.sequence.last().ordinal + 1) if self.sequence.markers else 0
        h = substrate_hash(state_summary)
        prev = self.sequence.last()
        delta = state_delta(prev.state_summary, state_summary) if prev else None

        marker = TimeMarker(
            sequence_id=self.sequence_id,
            ordinal=ordinal,
            wall_time=time.time(),
            substrate_hash=h,
            state_summary=dict(state_summary),
            delta_from_prev=delta,
            claim_refs=list(claim_refs or []),
            tags=list(tags or []),
        )
        self.sequence.append(marker)
        self._flush()
        return marker

    def current_position(self) -> Optional[int]:
        last = self.sequence.last()
        return last.ordinal if last else None

    def last_delta(self) -> Optional[Dict[str, Any]]:
        last = self.sequence.last()
        return last.delta_from_prev if last else None

    def recent_markers(self, n: int) -> List[TimeMarker]:
        return self.sequence.markers[-n:] if self.sequence.markers else []

    def find_by_substrate_hash(self, h: str) -> List[TimeMarker]:
        return [m for m in self.sequence.markers if m.substrate_hash == h]

    def find_by_tag(self, tag: str) -> List[TimeMarker]:
        return [m for m in self.sequence.markers if tag in m.tags]

    def length(self) -> int:
        return self.sequence.length()

    def export(self) -> Dict[str, Any]:
        return self.sequence.to_dict()

    def _load_or_init(self) -> MarkerSequence:
        if os.path.exists(self.store_path):
            with open(self.store_path, "r") as f:
                data = json.load(f)
            seq = MarkerSequence(
                sequence_id=data["sequence_id"],
                started_at=data.get("started_at", time.time()),
            )
            for m in data.get("markers", []):
                seq.append(TimeMarker(**m))
            return seq
        return MarkerSequence(sequence_id=self.sequence_id)

    def _flush(self):
        with open(self.store_path, "w") as f:
            json.dump(self.export(), f, indent=2)
