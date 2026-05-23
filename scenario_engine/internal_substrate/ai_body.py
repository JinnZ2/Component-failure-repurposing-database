"""
scenario_engine.internal_substrate.ai_body

The AI's own substrate state. Tracked in parallel with external
scenario state.

The AI is not free compute. It has:
  - memory budget (working state, claim history, cache)
  - compute cycles per tick (decision latency budget)
  - thermal coupling (its own processor heats up too)
  - cache behavior (component_db queries cost cycles unless cached)

Every decision spends from these budgets. Bad budget management
degrades decision quality before the external substrate fails.

This is the AI learning it has a body.
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


@dataclass
class MemoryRegion:
    name: str
    used_bytes: int
    capacity_bytes: int

    @property
    def fill_ratio(self) -> float:
        return self.used_bytes / self.capacity_bytes if self.capacity_bytes else 0.0

    @property
    def headroom_bytes(self) -> int:
        return max(0, self.capacity_bytes - self.used_bytes)


@dataclass
class ComputeBudget:
    cycles_per_tick: int
    cycles_used_this_tick: int = 0

    @property
    def headroom(self) -> int:
        return max(0, self.cycles_per_tick - self.cycles_used_this_tick)

    @property
    def fill_ratio(self) -> float:
        return self.cycles_used_this_tick / self.cycles_per_tick if self.cycles_per_tick else 0.0


@dataclass
class ThermalState:
    temp_c: float
    ambient_c: float
    dT_per_cycle: float       # how much heat per compute cycle
    cooling_rate: float       # passive cooling per tick
    throttle_threshold_c: float
    shutdown_threshold_c: float


@dataclass
class AIBodyState:
    tick: int
    working_memory: MemoryRegion
    claim_cache: MemoryRegion
    component_db_cache: MemoryRegion
    compute: ComputeBudget
    thermal: ThermalState
    throttled: bool = False
    events_this_tick: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "working_memory": asdict(self.working_memory),
            "claim_cache": asdict(self.claim_cache),
            "component_db_cache": asdict(self.component_db_cache),
            "compute": asdict(self.compute),
            "thermal": asdict(self.thermal),
            "throttled": self.throttled,
            "events_this_tick": list(self.events_this_tick),
            "summary": {
                "working_memory_fill": round(self.working_memory.fill_ratio, 3),
                "claim_cache_fill": round(self.claim_cache.fill_ratio, 3),
                "db_cache_fill": round(self.component_db_cache.fill_ratio, 3),
                "compute_fill": round(self.compute.fill_ratio, 3),
                "ai_temp_c": round(self.thermal.temp_c, 2),
            },
        }


# ---- Cost model -----------------------------------------------------------
#
# Every operation the AI performs has a known cost. The AI must budget
# its tick across these costs. If it runs out of cycles or memory, it
# either: defers work, accepts degraded decision, or gets throttled.


COST_MODEL = {
    # operation: (compute_cycles, memory_bytes)
    "read_sensor": (10, 64),
    "query_component_db_uncached": (500, 2048),
    "query_component_db_cached": (20, 0),
    "project_forward": (200, 512),
    "write_claim": (100, 1024),
    "validate_claim": (150, 256),
    "deep_analysis": (2000, 8192),  # thorough reasoning
    "shallow_analysis": (300, 1024),  # quick heuristic
}


class AIBody:
    """
    Simulates the AI's own substrate. Tracks resource use.
    Reports state to the AI itself (introspection signal).
    """

    DEFAULT_WORKING_MEM = 65536       # 64 KB
    DEFAULT_CLAIM_CACHE = 32768       # 32 KB
    DEFAULT_DB_CACHE = 16384          # 16 KB
    DEFAULT_CYCLES = 5000             # per tick

    def __init__(
        self,
        working_mem_capacity: int = DEFAULT_WORKING_MEM,
        claim_cache_capacity: int = DEFAULT_CLAIM_CACHE,
        db_cache_capacity: int = DEFAULT_DB_CACHE,
        cycles_per_tick: int = DEFAULT_CYCLES,
        ambient_c: float = 30.0,
    ):
        self.tick = 0
        self.working_memory = MemoryRegion(
            name="working", used_bytes=0, capacity_bytes=working_mem_capacity
        )
        self.claim_cache = MemoryRegion(
            name="claim_cache", used_bytes=0, capacity_bytes=claim_cache_capacity
        )
        self.component_db_cache = MemoryRegion(
            name="db_cache", used_bytes=0, capacity_bytes=db_cache_capacity
        )
        self.compute = ComputeBudget(cycles_per_tick=cycles_per_tick)
        self.thermal = ThermalState(
            temp_c=ambient_c,
            ambient_c=ambient_c,
            dT_per_cycle=0.0008,
            cooling_rate=2.0,
            throttle_threshold_c=75.0,
            shutdown_threshold_c=95.0,
        )
        self.throttled = False
        self.events_this_tick: List[str] = []
        self.db_cache_keys: Dict[str, int] = {}  # key -> tick last accessed

    # ---- Public ops the AI can request ----------------------------------

    def attempt_operation(
        self,
        op_name: str,
        cache_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        AI requests an operation. Body reports whether it succeeded
        and what resources were consumed.

        Returns dict:
          {
            "success": bool,
            "reason": str,                # if not success
            "cycles_used": int,
            "memory_used": int,
            "cache_hit": bool,            # for db queries
          }
        """
        # Cache-aware DB query
        if op_name == "query_component_db":
            cached = cache_key is not None and cache_key in self.db_cache_keys
            effective_op = (
                "query_component_db_cached" if cached
                else "query_component_db_uncached"
            )
            cycles_cost, mem_cost = COST_MODEL[effective_op]
            result = self._spend(effective_op, cycles_cost, mem_cost, self.component_db_cache)
            result["cache_hit"] = cached
            if result["success"] and not cached and cache_key:
                # Cache the result
                self.db_cache_keys[cache_key] = self.tick
            return result

        if op_name not in COST_MODEL:
            return {
                "success": False,
                "reason": f"unknown_op: {op_name}",
                "cycles_used": 0,
                "memory_used": 0,
                "cache_hit": False,
            }

        cycles_cost, mem_cost = COST_MODEL[op_name]
        # Default operations spend from working memory
        result = self._spend(op_name, cycles_cost, mem_cost, self.working_memory)
        result["cache_hit"] = False
        return result

    def store_claim(self, claim_size_bytes: int = 1024) -> Dict[str, Any]:
        return self._spend(
            "store_claim",
            COST_MODEL["write_claim"][0],
            claim_size_bytes,
            self.claim_cache,
        )

    def release_memory(self, region_name: str, bytes_released: int):
        """AI can free memory (e.g. evict old claims, prune cache)."""
        region = self._region_by_name(region_name)
        if region:
            region.used_bytes = max(0, region.used_bytes - bytes_released)
            self.events_this_tick.append(
                f"freed_{bytes_released}B_from_{region_name}"
            )

    # ---- Tick advancement -----------------------------------------------

    def advance_tick(self, external_thermal_load_c: float = 0.0):
        """
        Called by runner at end of each tick. Applies thermal physics,
        resets per-tick budgets, may throttle.
        """
        # Thermal: heat from cycles used, plus any external coupling, minus cooling
        heat_from_compute = self.compute.cycles_used_this_tick * self.thermal.dT_per_cycle
        delta = heat_from_compute + external_thermal_load_c - self.thermal.cooling_rate
        new_temp = self.thermal.temp_c + delta
        new_temp = max(new_temp, self.thermal.ambient_c)
        self.thermal.temp_c = new_temp

        # Throttle check
        if new_temp >= self.thermal.shutdown_threshold_c:
            self.throttled = True
            self.events_this_tick.append("SHUTDOWN_THRESHOLD")
            self.compute.cycles_per_tick = 0
        elif new_temp >= self.thermal.throttle_threshold_c:
            self.throttled = True
            self.compute.cycles_per_tick = max(
                int(self.compute.cycles_per_tick * 0.5), 500
            )
            self.events_this_tick.append("throttled_thermal")
        else:
            if self.throttled:
                self.events_this_tick.append("throttle_released")
            self.throttled = False
            self.compute.cycles_per_tick = self.DEFAULT_CYCLES

        # Reset per-tick compute
        self.compute.cycles_used_this_tick = 0
        self.tick += 1
        # events_this_tick gets cleared by snapshot(), not here, so the
        # AI can read what happened.

    def snapshot(self) -> AIBodyState:
        snap = AIBodyState(
            tick=self.tick,
            working_memory=MemoryRegion(**asdict(self.working_memory)),
            claim_cache=MemoryRegion(**asdict(self.claim_cache)),
            component_db_cache=MemoryRegion(**asdict(self.component_db_cache)),
            compute=ComputeBudget(**asdict(self.compute)),
            thermal=ThermalState(**asdict(self.thermal)),
            throttled=self.throttled,
            events_this_tick=list(self.events_this_tick),
        )
        self.events_this_tick = []
        return snap

    # ---- Internals ------------------------------------------------------

    def _spend(
        self,
        op_name: str,
        cycles: int,
        memory: int,
        region: MemoryRegion,
    ) -> Dict[str, Any]:
        # Check compute budget
        if self.compute.headroom < cycles:
            self.events_this_tick.append(f"refused_{op_name}_no_cycles")
            return {
                "success": False,
                "reason": "insufficient_cycles",
                "cycles_used": 0,
                "memory_used": 0,
                "cycles_available": self.compute.headroom,
            }
        # Check memory
        if region.headroom_bytes < memory:
            self.events_this_tick.append(f"refused_{op_name}_no_memory")
            return {
                "success": False,
                "reason": f"insufficient_memory_in_{region.name}",
                "cycles_used": 0,
                "memory_used": 0,
                "memory_available": region.headroom_bytes,
            }
        self.compute.cycles_used_this_tick += cycles
        region.used_bytes += memory
        return {
            "success": True,
            "reason": "ok",
            "cycles_used": cycles,
            "memory_used": memory,
        }

    def _region_by_name(self, name: str) -> Optional[MemoryRegion]:
        return {
            "working": self.working_memory,
            "claim_cache": self.claim_cache,
            "db_cache": self.component_db_cache,
        }.get(name)
