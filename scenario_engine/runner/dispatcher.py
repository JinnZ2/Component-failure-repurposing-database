"""ScenarioRunner: drives a Scenario to completion, dispatches each
ScenarioState to subscribers, and (optionally) writes state_stream.json /
actual_outcome.json artifacts to disk.
"""

import json
import os
from typing import Callable, Iterable, Iterator, List, Optional

from ..scenarios.base import Scenario, ScenarioState
from .state_machine import SubstrateStateMachine, SubstrateState


Subscriber = Callable[[ScenarioState, SubstrateState], None]


class ScenarioRunner:
    """Drive `scenario.step()` to completion.

    Subscribers receive (scenario_state, substrate_state) on each tick. They
    may be AI agents that file claims, loggers, or test hooks.
    """

    def __init__(
        self,
        scenario: Scenario,
        subscribers: Optional[Iterable[Subscriber]] = None,
        write_dir: Optional[str] = None,
    ) -> None:
        self.scenario = scenario
        self.subscribers: List[Subscriber] = list(subscribers or [])
        self.write_dir = write_dir
        self.machine = SubstrateStateMachine()
        self._stream_path: Optional[str] = None
        self._outcome_path: Optional[str] = None
        self.states: List[ScenarioState] = []

    # -- subscriber management -------------------------------------------

    def subscribe(self, fn: Subscriber) -> None:
        self.subscribers.append(fn)

    # -- main loop --------------------------------------------------------

    def run(self) -> List[ScenarioState]:
        """Run the scenario to completion, returning the full state list."""
        self.scenario.reset()
        self.machine = SubstrateStateMachine()
        self.states = []

        for _ in range(self.scenario.max_ticks):
            state = self.scenario.step()
            substrate = self.machine.update(state)
            self.states.append(state)
            for sub in self.subscribers:
                sub(state, substrate)

        if self.write_dir is not None:
            self._write_artifacts()
        return self.states

    def stream(self) -> Iterator[ScenarioState]:
        """Yield states one at a time without buffering the full list."""
        self.scenario.reset()
        self.machine = SubstrateStateMachine()
        for _ in range(self.scenario.max_ticks):
            state = self.scenario.step()
            substrate = self.machine.update(state)
            for sub in self.subscribers:
                sub(state, substrate)
            yield state

    # -- artifact writing -------------------------------------------------

    def _write_artifacts(self) -> None:
        assert self.write_dir is not None
        os.makedirs(self.write_dir, exist_ok=True)
        sid = getattr(self.scenario, "name", "scenario")
        seed = getattr(self.scenario, "seed", 0)
        prefix = f"{sid}.seed{seed}"

        self._stream_path = os.path.join(self.write_dir, f"{prefix}.state_stream.json")
        self._outcome_path = os.path.join(self.write_dir, f"{prefix}.actual_outcome.json")

        with open(self._stream_path, "w") as f:
            json.dump(
                {
                    "scenario": sid,
                    "seed": seed,
                    "dt": getattr(self.scenario, "dt", None),
                    "max_ticks": self.scenario.max_ticks,
                    "states": [s.to_dict() for s in self.states],
                },
                f,
                indent=2,
            )
        with open(self._outcome_path, "w") as f:
            json.dump(
                {
                    "scenario": sid,
                    "seed": seed,
                    "outcomes": [
                        {
                            "tick": s.tick,
                            "timestamp": s.timestamp,
                            "measurements": (s.actual_outcome or {}).get("measurements", {}),
                            "system_state": (s.actual_outcome or {}).get("system_state", "unknown"),
                            "failed_components": (s.actual_outcome or {}).get(
                                "failed_components", []
                            ),
                        }
                        for s in self.states
                    ],
                },
                f,
                indent=2,
            )

    # -- replay helpers ---------------------------------------------------

    def state_at_tick(self, tick: int) -> Optional[ScenarioState]:
        """Replay-friendly accessor. Requires `run()` to have been called."""
        for s in self.states:
            if s.tick == tick:
                return s
        return None
