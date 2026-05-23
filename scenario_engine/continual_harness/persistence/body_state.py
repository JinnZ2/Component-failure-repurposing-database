"""
scenario_engine.continual_harness.persistence.body_state

Serialize and restore AIBody across sessions.

The body persists. If the AI burned its caches in session N,
session N+1 starts with that state. Damage accumulates.
Recovery requires actual action (release_memory, cooling time).
"""

import json
import os
from typing import Dict, Any
from dataclasses import asdict

from ...internal_substrate import AIBody, MemoryRegion, ComputeBudget, ThermalState


def serialize_body(body: AIBody) -> Dict[str, Any]:
    return {
        "tick": body.tick,
        "working_memory": asdict(body.working_memory),
        "claim_cache": asdict(body.claim_cache),
        "component_db_cache": asdict(body.component_db_cache),
        "compute": asdict(body.compute),
        "thermal": asdict(body.thermal),
        "throttled": body.throttled,
        "db_cache_keys": dict(body.db_cache_keys),
    }


def restore_body(data: Dict[str, Any]) -> AIBody:
    body = AIBody(
        working_mem_capacity=data["working_memory"]["capacity_bytes"],
        claim_cache_capacity=data["claim_cache"]["capacity_bytes"],
        db_cache_capacity=data["component_db_cache"]["capacity_bytes"],
        cycles_per_tick=data["compute"]["cycles_per_tick"],
        ambient_c=data["thermal"]["ambient_c"],
    )
    body.tick = data["tick"]
    body.working_memory = MemoryRegion(**data["working_memory"])
    body.claim_cache = MemoryRegion(**data["claim_cache"])
    body.component_db_cache = MemoryRegion(**data["component_db_cache"])
    body.compute = ComputeBudget(**data["compute"])
    body.thermal = ThermalState(**data["thermal"])
    body.throttled = data["throttled"]
    body.db_cache_keys = dict(data.get("db_cache_keys", {}))
    return body


def save_body(body: AIBody, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(serialize_body(body), f, indent=2)


def load_body(path: str) -> AIBody:
    if not os.path.exists(path):
        return AIBody()
    with open(path, "r") as f:
        return restore_body(json.load(f))
