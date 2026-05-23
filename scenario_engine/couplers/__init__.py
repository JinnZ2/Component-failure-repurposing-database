"""
scenario_engine.couplers

Cross-substrate coupling models for the scenario library.

Adopts the dataclass + catalog shape from
JinnZ2/Geometric-to-Binary-Computational-Bridge/fabrication/couplers.py
(CC0). A coupler is a typed edge between two substrate domains carrying
a geometric ratio, separate from per-substrate physics. Scenarios apply
couplers to translate state in one domain into forcing on the next.

Upstream's catalog covers piezo / speaker / horn / pump — different
physics from our thermal → mechanical → electrical chain — so we keep
the shape and provide our own catalog entries.

License: CC0. Stdlib only.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Literal, Tuple


@dataclass(frozen=True)
class Coupler:
    """A typed edge between two substrate domains.

    kind:
      transformer: effort↔effort or flow↔flow,  y = ratio * x
      gyrator:     effort↔flow (different physical semantics),
                   same arithmetic in our scalar use.

    Kind is preserved so downstream bond-graph analyses can distinguish
    them, but `apply()` is the same.
    """
    name: str
    kind: Literal["transformer", "gyrator"]
    ratio: float
    port_in: str
    port_out: str
    geometry: Dict[str, Any] = field(default_factory=dict)
    provenance: str = "scenario_engine.couplers"

    def apply(self, x: float) -> float:
        return self.ratio * x


# Catalog of geometric → coupler mappings for scenario use.
# Each ratio_fn pulls its constants from a caller-supplied geometry dict
# so the same coupler kind can be instantiated for different
# configurations without editing this file.
CATALOG: Dict[str, Dict[str, Any]] = {
    "thermal_expansion_to_strain": {
        "kind": "transformer",
        "ratio_fn": lambda g: g["expansion_per_C_mm"],
        "ports": ("thermal", "mechanical"),
        "notes": "ΔT (C) → PCB region strain (mm). Linear regime only.",
    },
    "pcb_strain_to_cap_esr": {
        "kind": "gyrator",
        "ratio_fn": lambda g: g["esr_per_mm_strain"],
        "ports": ("mechanical", "electrical"),
        "notes": "PCB strain (mm) → bypass-cap ESR offset (ohm).",
    },
    "cap_esr_to_rail_noise": {
        "kind": "transformer",
        "ratio_fn": lambda g: g["noise_v_per_ohm_esr"],
        "ports": ("electrical", "electrical"),
        "notes": "ESR (ohm) → power rail noise (V), small-signal.",
    },
}


def build(name: str, geometry: Dict[str, Any]) -> Coupler:
    """Instantiate a Coupler from the catalog with a concrete geometry."""
    if name not in CATALOG:
        raise KeyError(
            f"unknown coupler: {name!r}. "
            f"available: {sorted(CATALOG.keys())}"
        )
    spec = CATALOG[name]
    return Coupler(
        name=name,
        kind=spec["kind"],
        ratio=spec["ratio_fn"](geometry),
        port_in=spec["ports"][0],
        port_out=spec["ports"][1],
        geometry=dict(geometry),
        provenance=f"scenario_engine.couplers.CATALOG[{name!r}]",
    )


__all__ = ["Coupler", "CATALOG", "build"]
