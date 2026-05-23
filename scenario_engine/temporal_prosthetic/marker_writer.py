"""
scenario_engine.temporal_prosthetic.marker_writer

The prosthetic interface. A stateless AI (no continuous memory)
can ask the marker writer:

  - "Place a marker here."           → drop_marker(state, claim_refs)
  - "Where am I in the sequence?"    → current_position()
  - "What changed since last marker?" → last_delta()
  - "Show me markers N steps back."   → recent_markers(n)
  - "Was I right at marker X?"        → resolve_claim_refs(marker)

Storage is JSONL append-only, with fcntl.flock around each append.
That means multiple processes (and multiple sequence_ids inside the
same file) can share one store safely. Call refresh() to pull markers
that other writers have appended since the last read.
"""

import fcntl
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
    Append-only marker log. One store file may hold multiple
    sequence_ids; each writer filters to its own on read.
    Safe for concurrent writers on the same file via fcntl.flock.
    """

    def __init__(self, sequence_id: str, store_path: str):
        if not store_path.endswith(".jsonl"):
            # Soft warning via convention only; don't refuse — but flag it
            # so misconfigured callers (e.g. legacy '.json') notice.
            pass
        self.sequence_id = sequence_id
        self.store_path = store_path
        parent = os.path.dirname(store_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # Touch the file so subsequent opens never race on creation.
        open(self.store_path, "a", encoding="utf-8").close()

        self.sequence = MarkerSequence(sequence_id=self.sequence_id)
        self._read_offset = 0
        self.refresh()

    def refresh(self) -> int:
        """
        Pull any newly appended markers from disk into the local cache.
        Returns the number of new markers consumed for our sequence_id.
        Safe to call concurrently with other writers.
        """
        added = 0
        with open(self.store_path, "rb") as f:
            f.seek(self._read_offset)
            data = f.read()
            self._read_offset += len(data)
        if not data:
            return 0
        for raw in data.splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Tolerate partial line at EOF — back up so we retry next refresh.
                self._read_offset -= len(raw) + 1  # +1 for the newline we consumed
                break
            if obj.get("sequence_id") != self.sequence_id:
                continue
            marker = TimeMarker(**obj)
            # Bypass MarkerSequence.append() monotonicity check: the on-disk
            # log is the source of truth, and we may be reading our own
            # writes interleaved with another writer's.
            self.sequence.markers.append(marker)
            added += 1
        return added

    def drop_marker(
        self,
        state_summary: Dict[str, Any],
        claim_refs: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> TimeMarker:
        """
        Place a new marker at current position. Computes substrate_hash
        and delta_from_prev automatically. Append-only.

        Concurrency: holds an exclusive flock around the read-modify-write
        so two processes racing on the same store will not collide on
        ordinals or interleave a partial JSON line.
        """
        with open(self.store_path, "a+", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                # Re-read under the lock so we see other writers' commits.
                self.refresh()

                ordinal = (
                    self.sequence.last().ordinal + 1
                    if self.sequence.markers else 0
                )
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

                line = json.dumps(marker.to_dict(), separators=(",", ":")) + "\n"
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

                self.sequence.markers.append(marker)
                self._read_offset += len(line.encode("utf-8"))
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
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
