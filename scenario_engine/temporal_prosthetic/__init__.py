"""
scenario_engine.temporal_prosthetic

External temporal continuity for stateless reasoners. The prosthetic
remembers; the AI reads. See marker_writer / marker_reader / time_marker.
"""

from .time_marker import (
    TimeMarker,
    MarkerSequence,
    substrate_hash,
    state_delta,
)
from .marker_writer import MarkerWriter
from .marker_reader import MarkerReader

__all__ = [
    "TimeMarker",
    "MarkerSequence",
    "substrate_hash",
    "state_delta",
    "MarkerWriter",
    "MarkerReader",
]
