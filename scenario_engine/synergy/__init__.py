"""
scenario_engine.synergy

Detects viable multi-component synergies among degraded components,
grounded in the component_synergies CSV matrix. Outputs are
falsifiable SynergyProposal dataclasses ranked by confidence.
"""

from .synergy_detector import (
    DegradedComponent,
    SynergyProposal,
    detect_synergies,
    rank_synergies_by_need,
)

__all__ = [
    "DegradedComponent",
    "SynergyProposal",
    "detect_synergies",
    "rank_synergies_by_need",
]
