"""
Synergy Matrix Explorer Simulation
====================================
Monte Carlo exploration of multi-component failure combinations.
Randomly pairs degraded components, scores emergent synergies, and
discovers non-obvious repurpose combinations.

Loads pairing rules derived from matrices/component_synergies.csv and
extends them with probabilistic discovery of novel pairings.

Evidence tier: Theoretical

Reference:
  - matrices/component_synergies.csv — known synergy pairs
  - components/diodes/silicon_diodes.md — diode + resistor thermal array
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

@dataclass
class DegradedComponent:
    name: str               # e.g. "Diode (Shorted)"
    component_type: str     # e.g. "diode"
    failure_mode: str       # e.g. "short_circuit"
    health: float           # 0.0 to 1.0
    properties: Dict[str, float]  # measurable residual properties


@dataclass
class SynergyRule:
    """A known or discovered pairing rule."""
    comp_a: str
    comp_b: str
    synergy_effect: str
    application: str
    base_effectiveness: float   # 0.0 to 1.0
    notes: str = ""


@dataclass
class SynergyResult:
    rule: SynergyRule
    actual_a: DegradedComponent
    actual_b: DegradedComponent
    score: float
    discovered: bool        # True if this was a novel discovery


# ---------------------------------------------------------------------------
# Known synergies (from component_synergies.csv)
# ---------------------------------------------------------------------------

KNOWN_SYNERGIES: List[SynergyRule] = [
    SynergyRule("Diode (Shorted)", "Resistor (Value Drift)",
                "Temperature coefficient + resistance drift",
                "Distributed thermal sensing", 0.85),
    SynergyRule("Diode (Open)", "Capacitor (Ceramic Drift)",
                "Parasitic capacitance + dielectric variation",
                "Timing circuit element", 0.55),
    SynergyRule("Resistor (Open)", "Inductor (Ferrite Core)",
                "Mechanical stability + magnetic field core",
                "Hybrid spacer/EMI choke", 0.50),
    SynergyRule("Capacitor (Shorted)", "Resistor (Shorted)",
                "Thermal + resistive load",
                "Emergency heating element", 0.40),
    SynergyRule("Transistor (Degraded Gain)", "Diode (Partial Degradation)",
                "Noise leakage + junction instability",
                "Random number generator", 0.80),
    SynergyRule("Inductor (Cracked Core)", "Capacitor (Value Drift)",
                "Modified inductance + capacitance shift",
                "Adaptive LC filter", 0.60),
    SynergyRule("Resistor (Open)", "Inductor (Open/Loop)",
                "Antenna geometry from leads/coil",
                "Emergency RF radiator", 0.65),
    SynergyRule("MOSFET (Shorted)", "LC Tank (Degraded)",
                "Low-ohm shunt for OOK keying",
                "Low-power beacon", 0.75),
    SynergyRule("Diode (Partial Degradation)", "MCU Timer",
                "Noise-derived ID/backoff",
                "Collision avoidance", 0.70),
    SynergyRule("Multiple Failed Resistors", "Multiple Failed Diodes",
                "Distributed resistance + capacitance",
                "Impedance network", 0.50),
]


# ---------------------------------------------------------------------------
# Component pool generator
# ---------------------------------------------------------------------------

def generate_component_pool(n: int = 30, seed: int = 42) -> List[DegradedComponent]:
    """Generate a random pool of degraded components."""
    rng = random.Random(seed)
    archetypes = [
        ("Diode (Shorted)", "diode", "short_circuit",
         {"resistance": (0.1, 2.0), "thermal_coeff": (0.001, 0.01)}),
        ("Diode (Partial Degradation)", "diode", "partial_degradation",
         {"leakage_ua": (0.1, 50.0), "noise_uv": (10.0, 500.0)}),
        ("Diode (Open)", "diode", "open_circuit",
         {"capacitance_pf": (0.5, 5.0), "lead_length_mm": (5.0, 25.0)}),
        ("Resistor (Value Drift)", "resistor", "value_drift",
         {"resistance": (100.0, 50000.0), "drift_pct": (5.0, 40.0)}),
        ("Resistor (Open)", "resistor", "open_circuit",
         {"lead_length_mm": (5.0, 20.0), "parasitic_pf": (0.1, 2.0)}),
        ("Resistor (Shorted)", "resistor", "short_circuit",
         {"resistance": (0.01, 1.0), "power_w": (0.1, 2.0)}),
        ("Capacitor (Ceramic Drift)", "capacitor", "value_drift",
         {"capacitance_pf": (10.0, 1000.0), "drift_pct": (10.0, 50.0)}),
        ("Capacitor (Value Drift)", "capacitor", "value_drift",
         {"capacitance_uf": (1.0, 100.0), "esr_ohm": (0.1, 5.0)}),
        ("Capacitor (Shorted)", "capacitor", "short_circuit",
         {"resistance": (0.01, 0.5), "energy_j": (0.0, 0.1)}),
        ("Transistor (Degraded Gain)", "transistor", "gain_loss",
         {"hfe": (5.0, 50.0), "noise_uv": (50.0, 2000.0)}),
        ("MOSFET (Shorted)", "transistor", "short_circuit",
         {"rds_on": (0.001, 0.1), "gate_charge_nc": (1.0, 50.0)}),
        ("Inductor (Ferrite Core)", "inductor", "partial_degradation",
         {"inductance_uh": (1.0, 100.0), "q_factor": (1.0, 20.0)}),
        ("Inductor (Cracked Core)", "inductor", "partial_degradation",
         {"inductance_uh": (0.5, 50.0), "srf_mhz": (1.0, 100.0)}),
        ("Inductor (Open/Loop)", "inductor", "open_circuit",
         {"loop_area_cm2": (0.5, 10.0), "wire_length_cm": (2.0, 30.0)}),
    ]

    pool: List[DegradedComponent] = []
    for _ in range(n):
        arch = rng.choice(archetypes)
        name, ctype, fmode, prop_ranges = arch
        health = round(rng.uniform(0.0, 0.6), 2)
        props = {k: round(rng.uniform(lo, hi), 4)
                 for k, (lo, hi) in prop_ranges.items()}
        pool.append(DegradedComponent(
            name=name, component_type=ctype, failure_mode=fmode,
            health=health, properties=props,
        ))
    return pool


# ---------------------------------------------------------------------------
# Synergy evaluator
# ---------------------------------------------------------------------------

class SynergyExplorer:
    """
    Evaluates pairs of degraded components for synergy potential.

    Known rules get a bonus. Unknown pairs are scored by a heuristic
    that rewards property complementarity (e.g., one component provides
    thermal output while the other provides sensing).
    """

    COMPLEMENTARY_PROPS = {
        ("resistance", "thermal_coeff"): 0.3,
        ("noise_uv", "leakage_ua"): 0.25,
        ("lead_length_mm", "loop_area_cm2"): 0.2,
        ("capacitance_pf", "inductance_uh"): 0.35,
        ("capacitance_uf", "inductance_uh"): 0.35,
        ("rds_on", "inductance_uh"): 0.2,
        ("power_w", "thermal_coeff"): 0.15,
    }

    def __init__(self, rules: Optional[List[SynergyRule]] = None):
        self.rules = rules or KNOWN_SYNERGIES
        self._rule_index: Dict[Tuple[str, str], SynergyRule] = {}
        for r in self.rules:
            self._rule_index[(r.comp_a, r.comp_b)] = r
            self._rule_index[(r.comp_b, r.comp_a)] = r

    def evaluate_pair(self, a: DegradedComponent,
                      b: DegradedComponent) -> Optional[SynergyResult]:
        key = (a.name, b.name)
        known_rule = self._rule_index.get(key)

        if known_rule:
            health_bonus = 1.0 - abs(a.health - b.health) * 0.5
            score = known_rule.base_effectiveness * health_bonus
            return SynergyResult(
                rule=known_rule, actual_a=a, actual_b=b,
                score=round(score, 3), discovered=False,
            )

        complementarity = self._property_complementarity(a, b)
        if complementarity > 0.1:
            novel_rule = SynergyRule(
                comp_a=a.name, comp_b=b.name,
                synergy_effect=f"Complementary properties ({complementarity:.2f})",
                application="[Novel — requires validation]",
                base_effectiveness=complementarity,
                notes="Discovered by Monte Carlo exploration",
            )
            return SynergyResult(
                rule=novel_rule, actual_a=a, actual_b=b,
                score=round(complementarity * 0.7, 3), discovered=True,
            )

        return None

    def _property_complementarity(self, a: DegradedComponent,
                                  b: DegradedComponent) -> float:
        score = 0.0
        for (p1, p2), bonus in self.COMPLEMENTARY_PROPS.items():
            if (p1 in a.properties and p2 in b.properties) or \
               (p2 in a.properties and p1 in b.properties):
                score += bonus
        if a.component_type != b.component_type:
            score += 0.1
        return min(score, 1.0)

    def monte_carlo(self, pool: List[DegradedComponent],
                    trials: int = 500,
                    seed: int = 42) -> List[SynergyResult]:
        rng = random.Random(seed)
        results: List[SynergyResult] = []
        seen: Set[Tuple[int, int]] = set()

        for _ in range(trials):
            i, j = rng.sample(range(len(pool)), 2)
            pair_key = (min(i, j), max(i, j))
            if pair_key in seen:
                continue
            seen.add(pair_key)

            result = self.evaluate_pair(pool[i], pool[j])
            if result and result.score > 0.15:
                results.append(result)

        results.sort(key=lambda r: r.score, reverse=True)
        return results


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run() -> None:
    print("Synergy Matrix Explorer Simulation")
    print("=" * 70)

    pool = generate_component_pool(n=40, seed=123)
    print(f"\nComponent pool: {len(pool)} degraded components")
    type_counts: Dict[str, int] = {}
    for c in pool:
        type_counts[c.component_type] = type_counts.get(c.component_type, 0) + 1
    for ctype, count in sorted(type_counts.items()):
        print(f"  {ctype:>12}: {count}")

    explorer = SynergyExplorer()
    results = explorer.monte_carlo(pool, trials=600, seed=123)

    known = [r for r in results if not r.discovered]
    novel = [r for r in results if r.discovered]

    print(f"\nTrials evaluated: 600")
    print(f"Synergies found: {len(results)} "
          f"({len(known)} known, {len(novel)} novel)")

    print(f"\n{'─' * 70}")
    print("  Top 10 Synergies (known + novel)")
    print(f"{'─' * 70}")
    print(f"  {'#':>3}  {'Score':>6}  {'Type':>8}  {'A':>28} + {'B':<28}")
    print(f"  {'':>3}  {'':>6}  {'':>8}  Application")
    print(f"  {'-' * 64}")

    for i, r in enumerate(results[:10], 1):
        tag = "known" if not r.discovered else "NOVEL"
        print(f"  {i:>3}  {r.score:>6.3f}  {tag:>8}  "
              f"{r.actual_a.name:>28} + {r.actual_b.name:<28}")
        print(f"  {'':>3}  {'':>6}  {'':>8}  -> {r.rule.application}")

    if novel:
        print(f"\n{'─' * 70}")
        print(f"  Novel Discoveries ({len(novel)} total, showing top 5)")
        print(f"{'─' * 70}")
        for i, r in enumerate(novel[:5], 1):
            print(f"\n  [{i}] {r.actual_a.name} + {r.actual_b.name}")
            print(f"      Score: {r.score:.3f} | Effect: {r.rule.synergy_effect}")
            print(f"      A health: {r.actual_a.health:.2f}, "
                  f"B health: {r.actual_b.health:.2f}")
            a_props = ", ".join(f"{k}={v}" for k, v in r.actual_a.properties.items())
            b_props = ", ".join(f"{k}={v}" for k, v in r.actual_b.properties.items())
            print(f"      A props: {a_props}")
            print(f"      B props: {b_props}")

    print(f"\n{'=' * 70}")
    print("  Note: Novel discoveries are theoretical and require")
    print("  experimental validation (Evidence Tier 1 -> Tier 3)")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    run()
