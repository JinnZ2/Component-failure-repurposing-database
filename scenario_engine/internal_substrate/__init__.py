"""Internal substrate: the AI's own body.

Tracks compute, memory, thermal coupling so the AI learns it isn't free.
"""

from .ai_body import (
    AIBody,
    AIBodyState,
    ComputeBudget,
    COST_MODEL,
    MemoryRegion,
    ThermalState,
)

__all__ = [
    "AIBody",
    "AIBodyState",
    "ComputeBudget",
    "COST_MODEL",
    "MemoryRegion",
    "ThermalState",
]
