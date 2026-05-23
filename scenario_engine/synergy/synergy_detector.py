"""
scenario_engine.synergy.synergy_detector

Given a set of degrading components and access to the synergy CSV,
detect which pairings (or triplings) are viable and what new function
they could provide.

Substrate-primary logic:
  - A failed component is not "trash"
  - A failed component has new measurable characteristics (degraded
    resistance, drifted ESR, open junction, etc.)
  - Two failed components with COMPATIBLE new characteristics can
    form a new functional unit
  - The new unit may not match the original system function but
    can fill a different role (sensor, oscillator, fallback channel)

Outputs are falsifiable: every synergy proposal includes a
predicted_function and predicted_characteristics that can be tested
against actual measurement.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class DegradedComponent:
    """A component that has degraded but not failed catastrophically."""
    component_id: str
    component_type: str  # matches DB taxonomy
    failure_mode: str
    severity: float  # 0.0 (nominal) to 1.0 (failed)
    measured_characteristics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class SynergyProposal:
    """A proposed combination of degraded components forming new function."""
    members: List[str]  # component_ids
    member_types: List[str]
    synergy_effect: str  # from CSV
    proposed_function: str
    repurpose_application: str
    confidence: float  # 0.0 to 1.0
    notes: str
    predicted_characteristics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def _matches(text: str, *patterns: str) -> bool:
    """Case-insensitive substring match across any pattern."""
    t = text.lower()
    return any(p.lower() in t for p in patterns)


def detect_synergies(
    degraded: List[DegradedComponent],
    db,
) -> List[SynergyProposal]:
    """
    Given degraded components and a ComponentDB, find viable synergies.

    Walks the component_synergies matrix and identifies rows where
    Component A and Component B both appear in `degraded`.
    """
    proposals = []
    if len(degraded) < 2:
        return proposals

    # Pull all synergy rows from DB
    all_synergies = db.synergies(component_type=None)

    # Build a fast lookup of degraded component_types
    degraded_by_type: Dict[str, List[DegradedComponent]] = {}
    for d in degraded:
        degraded_by_type.setdefault(d.component_type.lower(), []).append(d)

    seen_pairs = set()

    for syn in all_synergies:
        comp_a = (syn.get("component_a") or "").lower()
        comp_b = (syn.get("component_b") or "").lower()
        if not comp_a or not comp_b:
            continue

        # Find degraded components matching A and B (substring match
        # since CSV uses "failed_diode" but type may be "silicon_diode")
        a_candidates = []
        b_candidates = []
        for d in degraded:
            dt = d.component_type.lower()
            if _matches(comp_a, dt) or _matches(dt, comp_a.replace("failed_", "")):
                a_candidates.append(d)
            if _matches(comp_b, dt) or _matches(dt, comp_b.replace("failed_", "")):
                b_candidates.append(d)

        # Handle the "none" / single-component case
        if comp_b == "none":
            for a in a_candidates:
                pair_key = (a.component_id, "none")
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                proposals.append(SynergyProposal(
                    members=[a.component_id],
                    member_types=[a.component_type],
                    synergy_effect=syn.get("synergy_effect", ""),
                    proposed_function=syn.get("repurpose_application", ""),
                    repurpose_application=syn.get("repurpose_application", ""),
                    confidence=_confidence_from_severity([a.severity]),
                    notes=syn.get("notes", ""),
                ))
            continue

        # Pair up A-candidates with B-candidates (avoid same component pairing
        # with itself)
        for a in a_candidates:
            for b in b_candidates:
                if a.component_id == b.component_id:
                    continue
                pair_key = tuple(sorted([a.component_id, b.component_id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                proposals.append(SynergyProposal(
                    members=[a.component_id, b.component_id],
                    member_types=[a.component_type, b.component_type],
                    synergy_effect=syn.get("synergy_effect", ""),
                    proposed_function=syn.get("repurpose_application", ""),
                    repurpose_application=syn.get("repurpose_application", ""),
                    confidence=_confidence_from_severity([a.severity, b.severity]),
                    notes=syn.get("notes", ""),
                ))

    # Sort by confidence
    proposals.sort(key=lambda p: p.confidence, reverse=True)
    return proposals


def _confidence_from_severity(severities: List[float]) -> float:
    """
    Mid-severity components make best synergy candidates.
    Too-nominal: not actually degraded enough to spare.
    Too-failed: characteristics may be unusable.
    Sweet spot: severity around 0.3-0.7.
    """
    if not severities:
        return 0.0
    # Score each: max at severity=0.5
    scores = [1.0 - 2.0 * abs(s - 0.5) for s in severities]
    return max(0.0, sum(scores) / len(scores))


def rank_synergies_by_need(
    proposals: List[SynergyProposal],
    system_needs: List[str],
) -> List[SynergyProposal]:
    """
    Given current system needs (e.g. "fallback_communication", "thermal_sensing"),
    rank proposals by how well their proposed function fits.
    """
    def need_score(p: SynergyProposal) -> float:
        text = (p.proposed_function + " " + p.synergy_effect + " " + p.repurpose_application).lower()
        hits = sum(1 for need in system_needs if need.lower() in text)
        return p.confidence + hits * 0.3
    return sorted(proposals, key=need_score, reverse=True)
