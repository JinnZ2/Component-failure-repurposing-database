"""OutcomeChecker: grades each claim against the scenario's actual_outcome at
the predicted target tick.

Status:
  * VALIDATED   — every predicted target matched (within tolerance / categorically)
  * INVALIDATED — every predicted target failed
  * PARTIAL     — some matched, some failed

Validators never grade reasoning — only `prediction` vs actual measurements.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..claims.schema import Claim, CATEGORICAL_VALUES, _split_at_tick
from ..scenarios.base import ScenarioState


@dataclass
class Verdict:
    claim_id: str
    status: str                         # VALIDATED | INVALIDATED | PARTIAL
    error_margins: Dict[str, float] = field(default_factory=dict)
    within_tolerance: bool = False
    targets_evaluated: int = 0
    targets_matched: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "status": self.status,
            "error_margins": self.error_margins,
            "within_tolerance": self.within_tolerance,
            "targets_evaluated": self.targets_evaluated,
            "targets_matched": self.targets_matched,
            "notes": self.notes,
        }


class OutcomeChecker:
    """Indexes ScenarioStates by tick and evaluates claims against them."""

    def __init__(self, states: Iterable[ScenarioState]):
        self._by_tick: Dict[int, ScenarioState] = {s.tick: s for s in states}

    # -- public API -------------------------------------------------------

    def evaluate(self, claims: Iterable[Claim]) -> List[Verdict]:
        return [self.evaluate_one(c) for c in claims]

    def evaluate_one(self, claim: Claim) -> Verdict:
        targets = self._extract_targets(claim.prediction)
        tolerance = float(claim.prediction.get("tolerance", 0.0) or 0.0)

        if not targets:
            return Verdict(
                claim_id=claim.claim_id,
                status="INVALIDATED",
                notes="No falsifiable target keys.",
            )

        matched = 0
        margins: Dict[str, float] = {}
        notes: List[str] = []
        for key, value, target_tick in targets:
            state = self._by_tick.get(target_tick)
            if state is None:
                notes.append(f"{key}: no state at tick {target_tick}")
                margins[key] = float("inf")
                continue
            ok, err, why = self._check_one(state, key, value, tolerance)
            margins[key] = err
            if ok:
                matched += 1
            elif why:
                notes.append(f"{key}: {why}")

        total = len(targets)
        if matched == total:
            status = "VALIDATED"
            within = True
        elif matched == 0:
            status = "INVALIDATED"
            within = False
        else:
            status = "PARTIAL"
            within = False

        return Verdict(
            claim_id=claim.claim_id,
            status=status,
            error_margins=margins,
            within_tolerance=within,
            targets_evaluated=total,
            targets_matched=matched,
            notes="; ".join(notes),
        )

    # -- internals --------------------------------------------------------

    @staticmethod
    def _extract_targets(prediction: Dict[str, Any]) -> List[Tuple[str, Any, int]]:
        out: List[Tuple[str, Any, int]] = []
        for k, v in prediction.items():
            parsed = _split_at_tick(k)
            if parsed is None:
                continue
            base, target_tick = parsed
            out.append((k, v, target_tick))
        return out

    @staticmethod
    def _check_one(
        state: ScenarioState,
        key: str,
        predicted: Any,
        tolerance: float,
    ) -> Tuple[bool, float, str]:
        """Returns (matched, error_margin, note_if_failed)."""
        parsed = _split_at_tick(key)
        assert parsed is not None
        base, _ = parsed
        outcome = state.actual_outcome or {}

        # Categorical: system_state_at_tick_N => 'stable'/...
        if isinstance(predicted, str):
            if predicted not in CATEGORICAL_VALUES:
                return False, float("inf"), f"unknown category {predicted!r}"
            actual = outcome.get(base if base in outcome else "system_state",
                                 outcome.get("system_state", "unknown"))
            ok = (actual == predicted)
            return ok, 0.0 if ok else 1.0, "" if ok else f"actual={actual!r}"

        # Numeric: look up the named measurement.
        # Flat schema first (canonical scenarios put it directly in
        # actual_outcome); fall back to nested 'measurements' (legacy).
        if not isinstance(predicted, (int, float)) or isinstance(predicted, bool):
            return False, float("inf"), f"predicted has invalid type {type(predicted).__name__}"
        if base in outcome and not isinstance(outcome[base], (dict, list)):
            actual_raw = outcome[base]
        else:
            measurements = outcome.get("measurements", {}) or {}
            if base not in measurements:
                return False, float("inf"), f"no measurement named {base!r}"
            actual_raw = measurements[base]
        try:
            actual = float(actual_raw)
        except (TypeError, ValueError):
            return False, float("inf"), f"non-numeric actual={actual_raw!r}"
        err = abs(actual - float(predicted))
        ok = err <= tolerance
        return ok, err, "" if ok else f"|{actual} - {predicted}| = {err:.4f} > tol {tolerance}"
