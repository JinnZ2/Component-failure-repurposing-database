"""ClaimWriter: appends validated claims to CLAIM_TABLE.substrate.json."""

import json
import os
from typing import Any, Dict, List, Optional

from .schema import Claim, ClaimRejected, validate_claim


class ClaimWriter:
    """Append-only writer for CLAIM_TABLE.substrate.json.

    The file is a JSON object: {"claims": [Claim, ...]}.
    All claims are validated for falsifiability before being written.
    """

    def __init__(self, path: str):
        self.path = path
        self._claims: List[Claim] = []
        self._next_n: int = 1
        self._load_existing()

    # -- io ---------------------------------------------------------------

    def _load_existing(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r") as f:
            data = json.load(f)
        for raw in data.get("claims", []):
            c = Claim(**{k: v for k, v in raw.items() if k in Claim.__dataclass_fields__})
            self._claims.append(c)
        # advance auto-id counter past existing claim_ids
        used = set()
        for c in self._claims:
            if c.claim_id.startswith("claim_"):
                try:
                    used.add(int(c.claim_id.split("_", 1)[1]))
                except ValueError:
                    pass
        if used:
            self._next_n = max(used) + 1

    def _flush(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(
                {"claims": [c.to_dict() for c in self._claims]},
                f,
                indent=2,
            )

    # -- writing ----------------------------------------------------------

    def next_id(self) -> str:
        cid = f"claim_{self._next_n:04d}"
        self._next_n += 1
        return cid

    def file_claim(
        self,
        *,
        tick: int,
        event_detected: str,
        decision: str,
        reasoning: str,
        prediction: Dict[str, Any],
        scenario_id: Optional[str] = None,
        seed: Optional[int] = None,
        claim_id: Optional[str] = None,
    ) -> Claim:
        cid = claim_id or self.next_id()
        c = Claim(
            claim_id=cid,
            tick=int(tick),
            event_detected=event_detected,
            decision=decision,
            reasoning=reasoning,
            prediction=dict(prediction),
            falsifiable=True,
            status="pending",
            scenario_id=scenario_id,
            seed=seed,
        )
        validate_claim(c)   # raises ClaimRejected on bad input
        self._claims.append(c)
        self._flush()
        return c

    # -- read & update ---------------------------------------------------

    def claims(self) -> List[Claim]:
        return list(self._claims)

    def update_status(
        self,
        claim_id: str,
        status: str,
        validator_payload: Dict[str, Any],
    ) -> None:
        for c in self._claims:
            if c.claim_id == claim_id:
                c.status = status
                c.validator = dict(validator_payload)
                self._flush()
                return
        raise KeyError(f"claim_id {claim_id!r} not found")
