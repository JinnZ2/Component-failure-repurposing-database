"""ClaimTable: dict-based claim store for the Session orchestrator.

Companion to `ClaimWriter` (dataclass-based). Both write the same on-disk
schema, so they're interchangeable from the perspective of consumers.

Used by `scenario_engine.runner.session.Session`. Returns a `{"accepted": ...}`
verdict instead of raising — session.py prefers that shape.
"""

import json
import os
from typing import Any, Dict, List, Optional

from .schema import VALID_STATUS, is_falsifiable


class ClaimTable:
    """Append-only claim log keyed by `claim_id`."""

    def __init__(self, path: str):
        self.path = path
        self.claims: List[Dict[str, Any]] = []
        self._next_n = 1
        self._load()

    # -- io ---------------------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r") as f:
            data = json.load(f)
        self.claims = list(data.get("claims", []))
        used = set()
        for c in self.claims:
            cid = c.get("claim_id", "")
            if isinstance(cid, str) and cid.startswith("claim_"):
                try:
                    used.add(int(cid.split("_", 1)[1]))
                except ValueError:
                    pass
        if used:
            self._next_n = max(used) + 1

    def _flush(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({"claims": self.claims}, f, indent=2)

    # -- writing ----------------------------------------------------------

    def next_id(self) -> str:
        cid = f"claim_{self._next_n:04d}"
        self._next_n += 1
        return cid

    def write_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        # Mutate the caller's dict so they can reference `claim["claim_id"]`
        # afterward (session.py relies on this).
        if not claim.get("claim_id"):
            claim["claim_id"] = self.next_id()
        claim.setdefault("falsifiable", True)
        claim.setdefault("status", "pending")
        if claim["status"] not in VALID_STATUS:
            claim["status"] = "pending"
        if not isinstance(claim.get("prediction"), dict):
            return {
                "accepted": False,
                "reason": "prediction missing or not a dict",
                "claim_id": claim["claim_id"],
            }
        if not is_falsifiable(claim["prediction"]):
            return {
                "accepted": False,
                "reason": (
                    "prediction is not falsifiable: needs at least one "
                    "'<name>_at_tick_<N>' key, with numeric values requiring "
                    "'tolerance'"
                ),
                "claim_id": claim["claim_id"],
            }
        # Store a copy so later mutations to the caller's dict don't bleed in.
        self.claims.append(dict(claim))
        self._flush()
        return {"accepted": True, "claim_id": claim["claim_id"]}

    def update_status(
        self,
        claim_id: str,
        status: str,
        result: Dict[str, Any],
    ) -> None:
        for c in self.claims:
            if c.get("claim_id") == claim_id:
                c["status"] = status
                c["validator"] = dict(result)
                self._flush()
                return
        raise KeyError(f"claim_id {claim_id!r} not found")

    # -- audit ------------------------------------------------------------

    def audit_traceability(self) -> Dict[str, Any]:
        """
        Report which claims trace to a verified substrate-matrix row.

        Every claim that names a `decision` should also carry a
        `source_matrix_row` linking back to the CSV row that grounded
        that decision. Claims without it are "ungrounded" — internal
        heuristics with no audit trail to the component DB.

        Returns:
          {
            "total_claims": int,
            "decisions": int,                # claims that named a decision
            "grounded": int,                 # decisions with source_matrix_row
            "ungrounded": int,               # decisions without it
            "coverage": float | None,        # grounded / decisions
            "by_matrix": {matrix_name: int}, # grounded counts per matrix
            "ungrounded_claim_ids": [claim_id, ...],
          }
        """
        total = len(self.claims)
        decisions = 0
        grounded = 0
        ungrounded_ids: List[str] = []
        by_matrix: Dict[str, int] = {}
        for c in self.claims:
            if not c.get("decision"):
                continue
            decisions += 1
            src = c.get("source_matrix_row")
            if isinstance(src, dict) and src.get("matrix"):
                grounded += 1
                m = src["matrix"]
                by_matrix[m] = by_matrix.get(m, 0) + 1
            else:
                ungrounded_ids.append(c.get("claim_id", ""))
        coverage = (grounded / decisions) if decisions else None
        return {
            "total_claims": total,
            "decisions": decisions,
            "grounded": grounded,
            "ungrounded": decisions - grounded,
            "coverage": coverage,
            "by_matrix": by_matrix,
            "ungrounded_claim_ids": ungrounded_ids,
        }

    # -- summary ----------------------------------------------------------

    def accuracy_summary(self) -> Dict[str, Any]:
        total = len(self.claims)
        validated = sum(1 for c in self.claims if c.get("status") == "VALIDATED")
        invalidated = sum(1 for c in self.claims if c.get("status") == "INVALIDATED")
        partial = sum(1 for c in self.claims if c.get("status") == "PARTIAL")
        pending = sum(1 for c in self.claims if c.get("status") == "pending")
        graded = validated + invalidated + partial
        accuracy = (validated / graded) if graded else None
        partial_credit = (validated + 0.5 * partial) / graded if graded else None
        return {
            "total_claims": total,
            "validated": validated,
            "invalidated": invalidated,
            "partial": partial,
            "pending": pending,
            "graded": graded,
            "accuracy_validated_over_graded": accuracy,
            "score_partial_credit": partial_credit,
        }
