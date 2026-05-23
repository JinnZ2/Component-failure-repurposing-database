"""Tiny substrate state machine.

Tracks system_state transitions across ticks so subscribers (the AI) can react
to *changes*, not just current readings.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..scenarios.base import ScenarioState


VALID_STATES = ("stable", "degraded", "failed", "unknown")


@dataclass
class SubstrateState:
    """Running summary of substrate health across ticks."""
    system_state: str = "unknown"
    failed_components: List[str] = field(default_factory=list)
    last_tick: int = -1
    transitions: List[Tuple[int, str, str]] = field(default_factory=list)  # (tick, from, to)
    component_first_failure_tick: Dict[str, int] = field(default_factory=dict)


class SubstrateStateMachine:
    """Consumes ScenarioStates and maintains a SubstrateState summary."""

    def __init__(self) -> None:
        self.state = SubstrateState()

    def update(self, scenario_state: ScenarioState) -> SubstrateState:
        outcome = scenario_state.actual_outcome or {}
        new_system_state = str(outcome.get("system_state", "unknown"))
        if new_system_state not in VALID_STATES:
            new_system_state = "unknown"

        if self.state.system_state != new_system_state and self.state.last_tick >= 0:
            self.state.transitions.append(
                (scenario_state.tick, self.state.system_state, new_system_state)
            )

        for cid in outcome.get("failed_components", []) or []:
            if cid not in self.state.component_first_failure_tick:
                self.state.component_first_failure_tick[cid] = scenario_state.tick
            if cid not in self.state.failed_components:
                self.state.failed_components.append(cid)

        self.state.system_state = new_system_state
        self.state.last_tick = scenario_state.tick
        return self.state
