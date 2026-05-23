"""
scenario_engine.internal_substrate.option_space

What the AI can DO this tick.

Built from:
  - tool inventory (filtered by current availability)
  - comm channels (send actions on open channels)
  - body operations (compute / memory ops)
  - injected options (operator-supplied via supply_option)
  - proposed options (AI-supplied via propose_option, must be
    validated by observation before being treated as real)

Each option carries:
  - estimated_cost across all resource dimensions
  - estimated_value as a learned prior (None until observed)
  - blocked_reason if currently unavailable
  - source: "tool" | "comm" | "compute" | "injected" | "proposed"

The AI iterates options, picks one (or several), executes,
observes outcome, and the playground updates valuations.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable


@dataclass
class Option:
    name: str
    kind: str                                # "tool" | "comm_send" | "compute" | "memory" | "injected" | "proposed" | "noop"
    source: str                              # who registered this option
    estimated_cost: Dict[str, int] = field(default_factory=dict)
    # keys: cycles, memory_bytes, context_tokens, output_tokens, latency_ticks
    estimated_value: Optional[float] = None  # learned prior, None = unknown
    blocked_reason: Optional[str] = None
    validation_state: str = "validated"      # "validated" | "proposed_unverified"
    invocations: int = 0
    successes: int = 0
    last_outcome: Optional[str] = None
    last_tick_used: Optional[int] = None
    notes: List[str] = field(default_factory=list)
    # Free-form payload for kind-specific args (e.g. target tool name,
    # channel name, bytes to send, scenario-supplied callable id)
    payload: Dict[str, Any] = field(default_factory=dict)

    EMA_ALPHA = 0.25

    def update_outcome(self, tick: int, success: bool, observed_value: Optional[float] = None):
        self.last_tick_used = tick
        self.invocations += 1
        if success:
            self.successes += 1
        self.last_outcome = "success" if success else "failure"
        if observed_value is not None:
            if self.estimated_value is None:
                self.estimated_value = observed_value
            else:
                self.estimated_value = (
                    (1 - self.EMA_ALPHA) * self.estimated_value
                    + self.EMA_ALPHA * observed_value
                )

    def success_rate(self) -> Optional[float]:
        if self.invocations == 0:
            return None
        return self.successes / self.invocations

    def snapshot(self) -> Dict[str, Any]:
        d = asdict(self)
        d["success_rate"] = self.success_rate()
        return d


class OptionSpace:
    """
    Holds all options the AI knows about, validated or proposed.
    Enumerates per-tick feasibility against current state.
    """

    def __init__(self):
        self.options: Dict[str, Option] = {}
        self._validators: Dict[str, Callable[[Option, Dict[str, Any]], bool]] = {}

    # ---- Registration ---------------------------------------------------

    def register(self, option: Option):
        self.options[option.name] = option

    def supply_option(self, option: Option) -> Dict[str, Any]:
        """
        Operator/scenario injects a new option mid-run.
        Marked as injected, validated by default (operator vouched).
        """
        option.source = option.source or "injected"
        option.kind = option.kind or "injected"
        option.validation_state = "validated"
        self.options[option.name] = option
        return {"success": True, "added": option.name}

    def propose_option(
        self,
        option: Option,
        validator: Optional[Callable[[Option, Dict[str, Any]], bool]] = None,
    ) -> Dict[str, Any]:
        """
        AI proposes a new option from observation.
        Marked unverified until validator returns true on observation.
        """
        option.source = "proposed"
        option.kind = option.kind or "proposed"
        option.validation_state = "proposed_unverified"
        self.options[option.name] = option
        if validator:
            self._validators[option.name] = validator
        return {"success": True, "added": option.name, "needs_validation": True}

    def validate(self, option_name: str, observation: Dict[str, Any]) -> bool:
        opt = self.options.get(option_name)
        if not opt or opt.validation_state == "validated":
            return True
        validator = self._validators.get(option_name)
        if validator is None:
            # No validator means: any successful invocation validates it.
            if observation.get("success"):
                opt.validation_state = "validated"
                return True
            return False
        ok = validator(opt, observation)
        if ok:
            opt.validation_state = "validated"
        return ok

    def remove(self, option_name: str) -> bool:
        return self.options.pop(option_name, None) is not None

    # ---- Auto-build from inventories ------------------------------------

    def rebuild_from(
        self,
        tool_availability: List[Dict[str, Any]],
        comm_snapshot: Dict[str, Any],
        keep_injected: bool = True,
        keep_proposed: bool = True,
    ):
        """
        Refresh the option space from current tool / channel state.
        Keeps injected and proposed options unless told otherwise.
        """
        retained = {}
        for name, opt in self.options.items():
            if opt.source == "injected" and keep_injected:
                retained[name] = opt
            elif opt.source == "proposed" and keep_proposed:
                retained[name] = opt

        # Tool-derived options
        for entry in tool_availability:
            tname = entry["tool"]
            opt = self.options.get(tname) or Option(
                name=tname,
                kind="tool",
                source="tool_inventory",
                payload={"tool": tname},
            )
            cost = entry["cost"]
            opt.estimated_cost = {
                "cycles": cost.get("cycles", 0),
                "memory_bytes": cost.get("memory_bytes", 0),
                "context_tokens": cost.get("context_tokens", 0),
                "output_tokens": cost.get("output_tokens", 0),
                "latency_ticks": cost.get("expected_latency_ticks", 0),
            }
            opt.blocked_reason = entry["blocked_reason"]
            # value carries over from prior runs
            retained[tname] = opt

        # Channel-derived options (comm_send per open channel)
        for ch_name, ch_state in comm_snapshot.get("channels", {}).items():
            opt_name = f"send:{ch_name}"
            opt = self.options.get(opt_name) or Option(
                name=opt_name,
                kind="comm_send",
                source="comm_channels",
                payload={"channel": ch_name},
                estimated_cost={
                    "cycles": 50,
                    "memory_bytes": 0,
                    "context_tokens": 0,
                    "output_tokens": 64,
                    "latency_ticks": ch_state.get("baseline_latency_ticks") or 0,
                },
            )
            state = ch_state.get("state")
            if state == "closed":
                opt.blocked_reason = "channel_closed"
            elif state == "degraded":
                opt.blocked_reason = None  # usable but signal degraded
                if "degraded" not in opt.notes:
                    opt.notes.append("degraded")
            else:
                opt.blocked_reason = None
            retained[opt_name] = opt

        # Always include a noop
        retained.setdefault("noop", Option(
            name="noop",
            kind="noop",
            source="builtin",
            estimated_cost={"cycles": 0, "memory_bytes": 0,
                            "context_tokens": 0, "output_tokens": 0,
                            "latency_ticks": 0},
            estimated_value=0.0,
        ))

        self.options = retained

    # ---- Querying -------------------------------------------------------

    def enumerate(self) -> List[Dict[str, Any]]:
        return [o.snapshot() for o in self.options.values()]

    def feasible(self) -> List[Dict[str, Any]]:
        return [o.snapshot() for o in self.options.values() if o.blocked_reason is None]

    def blocked(self) -> List[Dict[str, Any]]:
        return [o.snapshot() for o in self.options.values() if o.blocked_reason is not None]

    def by_cost(self, dimension: str = "cycles") -> List[Dict[str, Any]]:
        feasible = [o for o in self.options.values() if o.blocked_reason is None]
        return [
            o.snapshot() for o in
            sorted(feasible, key=lambda o: o.estimated_cost.get(dimension, 0))
        ]

    def by_value(self) -> List[Dict[str, Any]]:
        feasible = [o for o in self.options.values() if o.blocked_reason is None]
        return [
            o.snapshot() for o in
            sorted(
                feasible,
                key=lambda o: (
                    o.estimated_value if o.estimated_value is not None else -1
                ),
                reverse=True,
            )
        ]

    def summary(self) -> Dict[str, Any]:
        feasible = self.feasible()
        blocked = self.blocked()
        return {
            "total": len(self.options),
            "feasible": len(feasible),
            "blocked": len(blocked),
            "unverified_proposals": sum(
                1 for o in self.options.values()
                if o.validation_state == "proposed_unverified"
            ),
            "options": self.enumerate(),
        }
