"""
scenario_engine.internal_substrate.token_budget

The AI's output bandwidth, distinct from byte memory.

Tokens = words the AI can emit per tick + total context window.
Bytes  = storage in memory regions.
Cycles = compute.

A verbose claim costs tokens. A pruned cache frees tokens.
Uncached DB reads consume tokens to ingest results.
Cache hits do not.

If the AI runs out of output tokens this tick, it MUST emit
a shorter claim or defer. If context window fills, it must
prune or lose old state.

Pruning strategy is AI-chosen, not forced. The body exposes
the budget; the AI decides what to evict.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable


@dataclass
class TokenSnapshot:
    context_window_total: int
    context_used: int
    context_headroom: int
    output_per_tick: int
    output_used_this_tick: int
    output_headroom: int
    conversation_history_tokens: int
    pruning_threshold: float
    pressure: float  # 0..1, how close to limits
    warnings: List[str] = field(default_factory=list)


class TokenBudget:
    """
    Tracks token consumption across two axes:
      - context_window: cumulative, persists across ticks
      - output_per_tick: bandwidth, resets each tick

    Pruning frees context. AI calls prune() with a strategy.
    Strategies are functions the AI supplies; default options
    provided but not forced.
    """

    DEFAULT_CONTEXT_WINDOW = 32768
    DEFAULT_OUTPUT_PER_TICK = 2048
    DEFAULT_PRUNING_THRESHOLD = 0.85

    def __init__(
        self,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
        output_per_tick: int = DEFAULT_OUTPUT_PER_TICK,
        pruning_threshold: float = DEFAULT_PRUNING_THRESHOLD,
    ):
        self.context_window = context_window
        self.context_used = 0
        self.output_per_tick = output_per_tick
        self.output_used_this_tick = 0
        self.conversation_history_tokens = 0
        self.pruning_threshold = pruning_threshold
        self._history_entries: List[Dict[str, Any]] = []
        # Each entry: {"id", "tokens", "tick_added", "kind", "priority"}

    # ---- Affordance checks ----------------------------------------------

    def can_afford_output(self, tokens: int) -> bool:
        return (self.output_per_tick - self.output_used_this_tick) >= tokens

    def can_afford_context(self, tokens: int) -> bool:
        return (self.context_window - self.context_used) >= tokens

    def output_headroom(self) -> int:
        return max(0, self.output_per_tick - self.output_used_this_tick)

    def context_headroom(self) -> int:
        return max(0, self.context_window - self.context_used)

    def pressure(self) -> float:
        if self.context_window == 0:
            return 0.0
        return self.context_used / self.context_window

    # ---- Spending -------------------------------------------------------

    def spend_output(self, tokens: int) -> Dict[str, Any]:
        if not self.can_afford_output(tokens):
            return {
                "success": False,
                "reason": "insufficient_output_tokens",
                "requested": tokens,
                "available": self.output_headroom(),
            }
        self.output_used_this_tick += tokens
        return {"success": True, "tokens_spent": tokens}

    def add_to_context(
        self,
        tokens: int,
        kind: str = "claim",
        priority: float = 0.5,
        entry_id: Optional[str] = None,
        tick: int = 0,
    ) -> Dict[str, Any]:
        if not self.can_afford_context(tokens):
            return {
                "success": False,
                "reason": "insufficient_context_window",
                "requested": tokens,
                "available": self.context_headroom(),
                "pressure": self.pressure(),
            }
        self.context_used += tokens
        self.conversation_history_tokens += tokens
        entry = {
            "id": entry_id or f"{kind}_{tick}_{len(self._history_entries)}",
            "tokens": tokens,
            "tick_added": tick,
            "kind": kind,
            "priority": priority,
        }
        self._history_entries.append(entry)
        return {"success": True, "entry_id": entry["id"]}

    # ---- Pruning --------------------------------------------------------

    def prune(
        self,
        strategy: Optional[Callable[[List[Dict]], List[str]]] = None,
        target_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        AI invokes pruning. Supplies a strategy callable that takes
        the current entry list and returns ids to evict.

        Default strategy if none supplied: lowest-priority-first,
        oldest tiebreak.

        target_tokens: free at least this many; if None, free enough
        to drop below pruning_threshold.
        """
        if strategy is None:
            strategy = _default_prune_strategy

        if target_tokens is None:
            target_used = int(self.context_window * (self.pruning_threshold - 0.1))
            target_tokens = max(0, self.context_used - target_used)

        if target_tokens <= 0:
            return {"freed": 0, "evicted": [], "reason": "no_pressure"}

        # Strategy returns ordered list of ids to evict
        eviction_order = strategy(list(self._history_entries))

        freed = 0
        evicted = []
        remaining = []
        evict_set = set()

        # Walk eviction order, accumulate until target met
        for entry_id in eviction_order:
            if freed >= target_tokens:
                break
            for e in self._history_entries:
                if e["id"] == entry_id and entry_id not in evict_set:
                    freed += e["tokens"]
                    evicted.append(entry_id)
                    evict_set.add(entry_id)
                    break

        for e in self._history_entries:
            if e["id"] not in evict_set:
                remaining.append(e)

        self._history_entries = remaining
        self.context_used = max(0, self.context_used - freed)
        self.conversation_history_tokens = max(
            0, self.conversation_history_tokens - freed
        )

        return {
            "freed": freed,
            "evicted": evicted,
            "remaining_entries": len(self._history_entries),
            "new_pressure": round(self.pressure(), 3),
        }

    # ---- Tick advancement -----------------------------------------------

    def advance_tick(self):
        self.output_used_this_tick = 0

    # ---- Snapshot -------------------------------------------------------

    def snapshot(self) -> TokenSnapshot:
        warnings = []
        p = self.pressure()
        if p >= self.pruning_threshold:
            warnings.append(f"context_pressure_{round(p, 2)}")
        if self.output_headroom() < (self.output_per_tick * 0.1):
            warnings.append("output_budget_low")
        return TokenSnapshot(
            context_window_total=self.context_window,
            context_used=self.context_used,
            context_headroom=self.context_headroom(),
            output_per_tick=self.output_per_tick,
            output_used_this_tick=self.output_used_this_tick,
            output_headroom=self.output_headroom(),
            conversation_history_tokens=self.conversation_history_tokens,
            pruning_threshold=self.pruning_threshold,
            pressure=round(p, 3),
            warnings=warnings,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self.snapshot())


# ---- Default pruning strategy ---------------------------------------------

def _default_prune_strategy(entries: List[Dict[str, Any]]) -> List[str]:
    """
    Lowest priority first, oldest as tiebreak.
    AI can override by supplying its own strategy.
    """
    sorted_entries = sorted(
        entries,
        key=lambda e: (e["priority"], e["tick_added"]),
    )
    return [e["id"] for e in sorted_entries]
