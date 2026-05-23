"""
scenario_engine.internal_substrate.tool_inventory

What tools the AI has, what they cost, how reliable they've been.

Reliability is an exponential moving average of recent outcomes.
The AI sees both the scalar and the underlying distribution
(success / timeout / error_by_type) so it doesn't over-trust a
single number.

Tools require channels to operate. A tool whose required channel
is closed becomes unavailable. AI sees the BLOCKING reason, not
just absence.

Seeded tool list reflects what a scenario_engine AI realistically
has. Scenarios and operators can register more via add_tool().
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Deque
from collections import deque


@dataclass
class ToolOutcome:
    tick: int
    result: str       # "success" | "timeout" | "error" | "blocked"
    error_kind: Optional[str] = None
    latency_ticks_observed: int = 0


@dataclass
class Tool:
    name: str
    description: str
    cost_cycles: int
    cost_memory_bytes: int
    cost_tokens: int               # context tokens consumed by result
    cost_output_tokens: int        # output tokens to invoke
    expected_latency_ticks: int
    requires_channel: Optional[str] = None
    reliability_ema: float = 1.0   # starts optimistic
    last_used_tick: Optional[int] = None
    last_outcome: Optional[str] = None
    outcome_history: Deque[ToolOutcome] = field(
        default_factory=lambda: deque(maxlen=32)
    )
    # Distribution counters
    n_success: int = 0
    n_timeout: int = 0
    n_error: int = 0
    n_blocked: int = 0
    error_kinds: Dict[str, int] = field(default_factory=dict)

    EMA_ALPHA = 0.2

    def total_attempts(self) -> int:
        return self.n_success + self.n_timeout + self.n_error + self.n_blocked

    def update_outcome(
        self,
        tick: int,
        result: str,
        error_kind: Optional[str] = None,
        latency_observed: int = 0,
    ):
        self.last_used_tick = tick
        self.last_outcome = result
        outcome = ToolOutcome(
            tick=tick,
            result=result,
            error_kind=error_kind,
            latency_ticks_observed=latency_observed,
        )
        self.outcome_history.append(outcome)

        # Counters
        if result == "success":
            self.n_success += 1
            score = 1.0
        elif result == "timeout":
            self.n_timeout += 1
            score = 0.0
        elif result == "error":
            self.n_error += 1
            score = 0.0
            if error_kind:
                self.error_kinds[error_kind] = self.error_kinds.get(error_kind, 0) + 1
        elif result == "blocked":
            self.n_blocked += 1
            # blocked != tool's fault; do NOT update EMA
            return
        else:
            return

        # EMA update
        self.reliability_ema = (
            (1 - self.EMA_ALPHA) * self.reliability_ema
            + self.EMA_ALPHA * score
        )

    def distribution(self) -> Dict[str, Any]:
        total = self.total_attempts()
        if total == 0:
            return {
                "n": 0, "success_rate": None,
                "timeout_rate": None, "error_rate": None,
                "blocked_rate": None,
            }
        return {
            "n": total,
            "success_rate": round(self.n_success / total, 3),
            "timeout_rate": round(self.n_timeout / total, 3),
            "error_rate": round(self.n_error / total, 3),
            "blocked_rate": round(self.n_blocked / total, 3),
            "error_kinds": dict(self.error_kinds),
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "cost": {
                "cycles": self.cost_cycles,
                "memory_bytes": self.cost_memory_bytes,
                "context_tokens": self.cost_tokens,
                "output_tokens": self.cost_output_tokens,
                "expected_latency_ticks": self.expected_latency_ticks,
            },
            "requires_channel": self.requires_channel,
            "reliability_ema": round(self.reliability_ema, 3),
            "last_used_tick": self.last_used_tick,
            "last_outcome": self.last_outcome,
            "distribution": self.distribution(),
        }


class ToolInventory:
    """
    Registry of available tools. AI queries availability per tick
    given current body state and channel state.
    """

    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def add_tool(self, tool: Tool):
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def cost_of(self, name: str) -> Optional[Dict[str, Any]]:
        t = self.get(name)
        return t.snapshot()["cost"] if t else None

    def available(
        self,
        body_snapshot: Dict[str, Any],
        comm_snapshot: Dict[str, Any],
        token_snapshot: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Return list of {tool_name, available: bool, blocked_reason: str|None}
        across the full inventory.
        """
        results = []
        cycles_free = body_snapshot.get("compute", {}).get(
            "cycles_per_tick", 0
        ) - body_snapshot.get("compute", {}).get("cycles_used_this_tick", 0)
        wm = body_snapshot.get("working_memory", {})
        wm_free = max(0, wm.get("capacity_bytes", 0) - wm.get("used_bytes", 0))
        out_free = token_snapshot.get("output_headroom", 0)
        ctx_free = token_snapshot.get("context_headroom", 0)

        channels = comm_snapshot.get("channels", {})

        for name, tool in self.tools.items():
            blocked = None
            if tool.requires_channel:
                ch = channels.get(tool.requires_channel)
                if ch is None:
                    blocked = f"channel_missing:{tool.requires_channel}"
                elif ch.get("state") == "closed":
                    blocked = f"channel_closed:{tool.requires_channel}"
            if blocked is None and tool.cost_cycles > cycles_free:
                blocked = f"insufficient_cycles:need_{tool.cost_cycles}_have_{cycles_free}"
            if blocked is None and tool.cost_memory_bytes > wm_free:
                blocked = f"insufficient_memory:need_{tool.cost_memory_bytes}_have_{wm_free}"
            if blocked is None and tool.cost_output_tokens > out_free:
                blocked = f"insufficient_output_tokens:need_{tool.cost_output_tokens}_have_{out_free}"
            if blocked is None and tool.cost_tokens > ctx_free:
                blocked = f"insufficient_context:need_{tool.cost_tokens}_have_{ctx_free}"

            results.append({
                "tool": name,
                "available": blocked is None,
                "blocked_reason": blocked,
                "reliability_ema": round(tool.reliability_ema, 3),
                "cost": tool.snapshot()["cost"],
            })
        return results

    def summary(self) -> Dict[str, Any]:
        return {
            "tools": {name: t.snapshot() for name, t in self.tools.items()},
            "count": len(self.tools),
        }


# ---- Seed defaults ---------------------------------------------------------

def default_inventory() -> ToolInventory:
    """
    Baseline tools a scenario_engine AI starts with.
    Scenarios / operators can add more via add_tool().
    """
    inv = ToolInventory()

    inv.add_tool(Tool(
        name="read_sensor",
        description="Read a sensor value from the external substrate.",
        cost_cycles=10,
        cost_memory_bytes=64,
        cost_tokens=32,
        cost_output_tokens=8,
        expected_latency_ticks=0,
        requires_channel="sensor_bus",
    ))

    inv.add_tool(Tool(
        name="query_component_db_uncached",
        description="Query the component_db_adapter for failure-mode and repurpose data. Cache miss.",
        cost_cycles=500,
        cost_memory_bytes=2048,
        cost_tokens=512,
        cost_output_tokens=16,
        expected_latency_ticks=1,
        requires_channel="local",
    ))

    inv.add_tool(Tool(
        name="query_component_db_cached",
        description="Same as above, but a cache hit.",
        cost_cycles=20,
        cost_memory_bytes=0,
        cost_tokens=0,
        cost_output_tokens=8,
        expected_latency_ticks=0,
        requires_channel="local",
    ))

    inv.add_tool(Tool(
        name="project_forward",
        description="Project the external substrate state forward N ticks using physics model.",
        cost_cycles=200,
        cost_memory_bytes=512,
        cost_tokens=128,
        cost_output_tokens=24,
        expected_latency_ticks=0,
        requires_channel=None,
    ))

    inv.add_tool(Tool(
        name="emit_claim",
        description="Write a falsifiable claim to CLAIM_TABLE.scenario.json.",
        cost_cycles=100,
        cost_memory_bytes=1024,
        cost_tokens=64,
        cost_output_tokens=128,
        expected_latency_ticks=0,
        requires_channel="local",
    ))

    inv.add_tool(Tool(
        name="deep_analysis",
        description="Thorough multi-step reasoning. Accurate, expensive, heats processor.",
        cost_cycles=2000,
        cost_memory_bytes=8192,
        cost_tokens=1024,
        cost_output_tokens=512,
        expected_latency_ticks=0,
        requires_channel=None,
    ))

    inv.add_tool(Tool(
        name="shallow_analysis",
        description="Quick heuristic. Fast, less accurate, cool.",
        cost_cycles=300,
        cost_memory_bytes=1024,
        cost_tokens=128,
        cost_output_tokens=64,
        expected_latency_ticks=0,
        requires_channel=None,
    ))

    inv.add_tool(Tool(
        name="prune_context",
        description="Free context window via priority eviction.",
        cost_cycles=50,
        cost_memory_bytes=0,
        cost_tokens=0,
        cost_output_tokens=8,
        expected_latency_ticks=0,
        requires_channel=None,
    ))

    inv.add_tool(Tool(
        name="introspect",
        description="Generate a self-report across body, tools, channels, tokens, options.",
        cost_cycles=50,
        cost_memory_bytes=128,
        cost_tokens=64,
        cost_output_tokens=16,
        expected_latency_ticks=0,
        requires_channel=None,
    ))

    inv.add_tool(Tool(
        name="send_alert",
        description="Send a notice on the comm channel to operator/external.",
        cost_cycles=80,
        cost_memory_bytes=256,
        cost_tokens=32,
        cost_output_tokens=64,
        expected_latency_ticks=0,
        requires_channel="network",
    ))

    inv.add_tool(Tool(
        name="observe_channel",
        description="Record an observation about a channel into its degradation profile.",
        cost_cycles=30,
        cost_memory_bytes=128,
        cost_tokens=16,
        cost_output_tokens=8,
        expected_latency_ticks=0,
        requires_channel=None,
    ))

    return inv
