"""
scenario_engine.environment

Environmental conditions that affect failure rates and synergy
viability. Two layers: instantaneous conditions, and cumulative
memory (damage that does not heal). See environment_state for the
EnvironmentState + EnvironmentalMemory dataclasses and the
acceleration_factor() multiplier.

`Environment` is exported as a shorthand alias for `EnvironmentState`
so spec text that says "from ..environment import Environment" works.
"""

from .environment_state import (
    EnvironmentState,
    EnvironmentalMemory,
)
from .synergy_validity import (
    SYNERGY_GATES,
    evaluate_synergy,
)

# Shorthand alias.
Environment = EnvironmentState

__all__ = [
    "EnvironmentState",
    "EnvironmentalMemory",
    "Environment",
    "SYNERGY_GATES",
    "evaluate_synergy",
]
