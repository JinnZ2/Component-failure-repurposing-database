"""
scenario_engine.internal_substrate.introspection

The single API the AI calls to know itself.

Aggregates body, tools, channels, tokens, options into a unified
report. Generates warnings from cross-subsystem signals (e.g.
"context full + degraded comm channel + low reliability tool"
is a different warning than any of those alone).

Introspection is NOT free. Each full() call spends cycles and
memory from the body. This is the design: the AI cannot have
omniscient self-knowledge for zero cost.

If the AI needs to check itself often, it pays often. If the
AI overspends on self-checks, it has less budget for action.
That tradeoff is the point.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


INTROSPECTION_COST_CYCLES = 50
INTROSPECTION_COST_MEMORY = 128


@dataclass
class IntrospectionReport:
    tick: int
    body: Dict[str, Any]
    tools: Dict[str, Any]
    channels: Dict[str, Any]
    tokens: Dict[str, Any]
    options: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    headroom: Dict[str, Any] = field(default_factory=dict)
    cost_paid: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SelfReport:
    """
    Aggregator. Holds references to all five subsystems and the body
    (for cost payment on each call).
    """

    def __init__(
        self,
        body,                # AIBody
        tool_inventory,      # ToolInventory
        comm_channels,       # CommChannels
        token_budget,        # TokenBudget
        option_space,        # OptionSpace
        cost_cycles: int = INTROSPECTION_COST_CYCLES,
        cost_memory: int = INTROSPECTION_COST_MEMORY,
    ):
        self.body = body
        self.tool_inventory = tool_inventory
        self.comm_channels = comm_channels
        self.token_budget = token_budget
        self.option_space = option_space
        self.cost_cycles = cost_cycles
        self.cost_memory = cost_memory

    # ---- Main entry -----------------------------------------------------

    def full(self, refresh_options: bool = True) -> IntrospectionReport:
        """
        Generate the unified self-report.

        Pays introspection cost from body. If body refuses, returns
        a stripped report with the refusal as a warning — the AI
        learns it cannot introspect right now.
        """
        cost_result = self.body.attempt_operation("read_sensor")
        # We piggyback on read_sensor cost model but charge our own values.
        # For more honest accounting we use the body's _spend directly:
        # but to keep the body API stable we use attempt + accept its cost.

        if not cost_result["success"]:
            return IntrospectionReport(
                tick=self.body.tick,
                body={},
                tools={},
                channels={},
                tokens={},
                options={},
                warnings=[
                    f"introspection_refused:{cost_result.get('reason', 'unknown')}",
                ],
                headroom={},
                cost_paid={"cycles": 0, "memory_bytes": 0},
            )

        body_snap = self.body.snapshot().to_dict()
        token_snap = self.token_budget.to_dict()
        comm_snap = self.comm_channels.summary()
        tool_avail = self.tool_inventory.available(
            body_snap, comm_snap, token_snap
        )
        tool_summary = self.tool_inventory.summary()
        tool_summary["availability"] = tool_avail

        if refresh_options:
            self.option_space.rebuild_from(tool_avail, comm_snap)
        opt_summary = self.option_space.summary()

        warnings = self._cross_subsystem_warnings(
            body_snap, token_snap, comm_snap, tool_avail, opt_summary
        )
        headroom = self._headroom(body_snap, token_snap, comm_snap)

        return IntrospectionReport(
            tick=self.body.tick,
            body=body_snap,
            tools=tool_summary,
            channels=comm_snap,
            tokens=token_snap,
            options=opt_summary,
            warnings=warnings,
            headroom=headroom,
            cost_paid={
                "cycles": cost_result.get("cycles_used", 0),
                "memory_bytes": cost_result.get("memory_used", 0),
            },
        )

    # ---- Lightweight queries (no cost) ----------------------------------
    # These exist for the runner / external code, not for the AI.

    def quick_warnings(self) -> List[str]:
        body_snap = self.body.snapshot().to_dict()
        token_snap = self.token_budget.to_dict()
        comm_snap = self.comm_channels.summary()
        return self._cross_subsystem_warnings(
            body_snap, token_snap, comm_snap, [], {}
        )

    # ---- Internals ------------------------------------------------------

    def _cross_subsystem_warnings(
        self,
        body_snap: Dict[str, Any],
        token_snap: Dict[str, Any],
        comm_snap: Dict[str, Any],
        tool_avail: List[Dict[str, Any]],
        opt_summary: Dict[str, Any],
    ) -> List[str]:
        warnings: List[str] = []

        # Body-level
        if body_snap.get("throttled"):
            warnings.append("body_throttled")
        if body_snap.get("summary", {}).get("ai_temp_c", 0) > 70:
            warnings.append(f"thermal_high_{body_snap['summary']['ai_temp_c']}c")
        wm_fill = body_snap.get("summary", {}).get("working_memory_fill", 0)
        if wm_fill > 0.85:
            warnings.append(f"working_memory_pressure_{round(wm_fill, 2)}")
        compute_fill = body_snap.get("summary", {}).get("compute_fill", 0)
        if compute_fill > 0.9:
            warnings.append(f"compute_saturated_{round(compute_fill, 2)}")

        # Token-level
        for w in token_snap.get("warnings", []):
            warnings.append(f"token_{w}")

        # Channel-level
        counts = comm_snap.get("counts", {})
        if counts.get("closed", 0) > 0:
            warnings.append(f"channels_closed_{counts['closed']}")
        if counts.get("degraded", 0) > 0:
            warnings.append(f"channels_degraded_{counts['degraded']}")
        if counts.get("open", 0) == 0 and len(comm_snap.get("channels", {})) > 0:
            warnings.append("no_open_channels")

        # Tool-level
        unreliable = [
            t["tool"] for t in tool_avail
            if t.get("reliability_ema", 1.0) < 0.5
        ]
        if unreliable:
            warnings.append(f"low_reliability_tools:{','.join(unreliable)}")

        # Option-level
        if opt_summary:
            if opt_summary.get("feasible", 0) <= 1:  # only noop left
                warnings.append("option_space_collapsed")
            unverified = opt_summary.get("unverified_proposals", 0)
            if unverified > 0:
                warnings.append(f"unverified_proposals_{unverified}")

        # Cross-cutting compound warnings
        critical_compound = (
            "body_throttled" in warnings
            and any(w.startswith("token_") for w in warnings)
            and "channels_degraded" in " ".join(warnings)
        )
        if critical_compound:
            warnings.append("COMPOUND_DEGRADATION")

        return warnings

    def _headroom(
        self,
        body_snap: Dict[str, Any],
        token_snap: Dict[str, Any],
        comm_snap: Dict[str, Any],
    ) -> Dict[str, Any]:
        wm = body_snap.get("working_memory", {})
        cc = body_snap.get("claim_cache", {})
        db = body_snap.get("component_db_cache", {})
        compute = body_snap.get("compute", {})

        return {
            "cycles": max(0, compute.get("cycles_per_tick", 0)
                          - compute.get("cycles_used_this_tick", 0)),
            "working_memory_bytes": max(0, wm.get("capacity_bytes", 0)
                                        - wm.get("used_bytes", 0)),
            "claim_cache_bytes": max(0, cc.get("capacity_bytes", 0)
                                     - cc.get("used_bytes", 0)),
            "db_cache_bytes": max(0, db.get("capacity_bytes", 0)
                                  - db.get("used_bytes", 0)),
            "output_tokens": token_snap.get("output_headroom", 0),
            "context_tokens": token_snap.get("context_headroom", 0),
            "open_channels": comm_snap.get("counts", {}).get("open", 0),
        }
