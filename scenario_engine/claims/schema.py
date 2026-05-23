"""Claim schema.

A claim is a falsifiable prediction the AI files at one tick about the state
of the substrate at a later tick. Predictions MUST include numeric values with
tolerance, OR a categorical label drawn from a fixed vocabulary.

Schema matches the interface contract:

```json
{
  "claim_id": "claim_0001",
  "tick": 0,
  "event_detected": "thermal_drift_Q1",
  "decision": "reroute_load_to_Q2",
  "reasoning": "Q1 at 87C, dT/dt = 0.4C/s, projected breach in 95s",
  "prediction": {
    "Q1_temp_c_at_tick_100": 85.0,
    "system_state_at_tick_100": "stable",
    "tolerance": 5.0
  },
  "falsifiable": true,
  "status": "pending"
}
```

Validators never grade reasoning — only `prediction` vs actual measurements.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional


# Valid categorical predictions
CATEGORICAL_VALUES = frozenset({"stable", "degraded", "failed", "unknown"})

# Valid statuses
VALID_STATUS = frozenset({"pending", "VALIDATED", "INVALIDATED", "PARTIAL"})


class PredictionType:
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


class ClaimRejected(ValueError):
    """Raised when a claim fails falsifiability validation at write time."""


@dataclass
class Claim:
    claim_id: str
    tick: int                       # tick the claim was filed at
    event_detected: str             # human label, ungraded
    decision: str                   # action the AI took, ungraded
    reasoning: str                  # ungraded
    prediction: Dict[str, Any]      # MUST contain at least one *_at_tick_N key + 'tolerance'
    falsifiable: bool = True
    status: str = "pending"
    # filled in by the validator
    validator: Dict[str, Any] = field(default_factory=dict)
    scenario_id: Optional[str] = None
    seed: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Falsifiability checks
# ---------------------------------------------------------------------------

def _split_at_tick(key: str):
    """Return (base, tick) for keys like 'Q1_temp_c_at_tick_100'."""
    marker = "_at_tick_"
    idx = key.rfind(marker)
    if idx < 0:
        return None
    base = key[:idx]
    try:
        tick = int(key[idx + len(marker):])
    except ValueError:
        return None
    return base, tick


def is_falsifiable(prediction: Dict[str, Any]) -> bool:
    """A prediction is falsifiable if:

    * It contains at least one `<name>_at_tick_<N>` entry, AND
    * Each such entry is either:
        - numeric (int/float)  AND `tolerance` (numeric, >=0) is present, OR
        - one of the CATEGORICAL_VALUES.
    """
    if not isinstance(prediction, dict) or not prediction:
        return False
    has_numeric = False
    targets = []
    for k, v in prediction.items():
        parsed = _split_at_tick(k)
        if parsed is None:
            continue
        targets.append((k, v))
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            has_numeric = True
        elif isinstance(v, str):
            if v not in CATEGORICAL_VALUES:
                return False
        else:
            return False
    if not targets:
        return False
    if has_numeric:
        tol = prediction.get("tolerance", None)
        if not isinstance(tol, (int, float)) or isinstance(tol, bool):
            return False
        if tol < 0:
            return False
    return True


def validate_claim(c: Claim) -> None:
    """Raise ClaimRejected if `c` is not a well-formed falsifiable claim."""
    if not c.claim_id or not isinstance(c.claim_id, str):
        raise ClaimRejected("claim_id missing or non-string")
    if not isinstance(c.tick, int) or c.tick < 0:
        raise ClaimRejected("tick must be a non-negative int")
    if not isinstance(c.prediction, dict):
        raise ClaimRejected("prediction must be a dict")
    if c.status not in VALID_STATUS:
        raise ClaimRejected(f"status must be one of {sorted(VALID_STATUS)}")
    if not is_falsifiable(c.prediction):
        raise ClaimRejected(
            "prediction is not falsifiable: needs at least one "
            "'<name>_at_tick_<N>' key, with numeric values requiring 'tolerance'"
        )
    if not c.falsifiable:
        raise ClaimRejected("claim explicitly marked non-falsifiable; rejected")
