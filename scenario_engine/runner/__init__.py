"""Runner: dispatches scenario readings through a small state machine and
forwards them to subscribers; or orchestrates a full session pairing external
substrate with internal substrate (AIBody)."""

from .dispatcher import ScenarioRunner, Subscriber
from .session import OpInterface, Session
from .state_machine import SubstrateState, SubstrateStateMachine

__all__ = [
    "ScenarioRunner",
    "Subscriber",
    "Session",
    "OpInterface",
    "SubstrateStateMachine",
    "SubstrateState",
]
