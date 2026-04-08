"""
Repurpose Decision Router Simulation
======================================
Decision interface that evaluates a degraded component's health snapshot
and routes it to the best repurposing application using a scored rule
engine.

The router implements three interface patterns:
  1. Rule-based scoring — weighted criteria match
  2. Threshold gating — hard pass/fail on safety and viability
  3. Ranked output — sorted list of viable repurpose options

Evidence tier: Theoretical

Reference:
  - matrices/failure_mode_matrix.csv — failure-to-repurpose mappings
  - matrices/repurpose_effectiveness.csv — effectiveness ratings
  - binary_sensor.md — health score, failure mode classification
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class Effectiveness(Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

    @property
    def score(self) -> float:
        return {"High": 1.0, "Medium": 0.6, "Low": 0.3}[self.value]


class FailureMode(Enum):
    VALUE_DRIFT = "value_drift"
    SHORT_CIRCUIT = "short_circuit"
    OPEN_CIRCUIT = "open_circuit"
    PARTIAL_DEGRADATION = "partial_degradation"
    ESR_RISE = "esr_rise"
    LEAKAGE_INCREASE = "leakage_increase"
    GAIN_LOSS = "gain_loss"


@dataclass
class ComponentHealth:
    component_type: str          # e.g. "resistor", "diode", "capacitor"
    failure_mode: FailureMode
    health_score: float          # 0.0 to 1.0
    drift_pct: float
    temperature_c: float = 25.0
    notes: str = ""


@dataclass
class RepurposeOption:
    application: str
    effectiveness: Effectiveness
    min_health: float           # minimum health to be viable
    max_health: float           # above this, component isn't degraded enough
    compatible_modes: List[FailureMode]
    safety_critical: bool = False
    description: str = ""


@dataclass
class RoutingResult:
    option: RepurposeOption
    score: float                # 0.0 to 1.0 composite score
    gate_pass: bool
    reasoning: str


# ---------------------------------------------------------------------------
# Repurpose knowledge base (derived from matrices/)
# ---------------------------------------------------------------------------

REPURPOSE_OPTIONS: List[RepurposeOption] = [
    RepurposeOption(
        application="Temperature sensor (thermal coefficient)",
        effectiveness=Effectiveness.HIGH,
        min_health=0.1, max_health=0.7,
        compatible_modes=[FailureMode.VALUE_DRIFT, FailureMode.PARTIAL_DEGRADATION],
        description="Use drifted resistor's temperature coefficient as a sensing element",
    ),
    RepurposeOption(
        application="Current limiter (fixed high-R)",
        effectiveness=Effectiveness.MEDIUM,
        min_health=0.2, max_health=0.8,
        compatible_modes=[FailureMode.VALUE_DRIFT],
        description="Drifted-high resistor acts as passive current limiter",
    ),
    RepurposeOption(
        application="Heating element",
        effectiveness=Effectiveness.MEDIUM,
        min_health=0.0, max_health=0.5,
        compatible_modes=[FailureMode.SHORT_CIRCUIT, FailureMode.VALUE_DRIFT],
        description="Shorted or low-R component dissipates heat for thermal signaling",
    ),
    RepurposeOption(
        application="Entropy source (noise harvesting)",
        effectiveness=Effectiveness.HIGH,
        min_health=0.05, max_health=0.6,
        compatible_modes=[FailureMode.PARTIAL_DEGRADATION, FailureMode.LEAKAGE_INCREASE,
                          FailureMode.GAIN_LOSS],
        description="Junction noise from degraded semiconductor feeds an RNG",
    ),
    RepurposeOption(
        application="Crude RC timing element",
        effectiveness=Effectiveness.LOW,
        min_health=0.1, max_health=0.6,
        compatible_modes=[FailureMode.VALUE_DRIFT, FailureMode.ESR_RISE],
        description="Drifted R or C still usable for non-precision timing",
    ),
    RepurposeOption(
        application="Voltage reference (zener-mode)",
        effectiveness=Effectiveness.MEDIUM,
        min_health=0.2, max_health=0.7,
        compatible_modes=[FailureMode.PARTIAL_DEGRADATION, FailureMode.LEAKAGE_INCREASE],
        description="Degraded diode with stable breakdown as crude voltage reference",
    ),
    RepurposeOption(
        application="Antenna element (lead/coil geometry)",
        effectiveness=Effectiveness.MEDIUM,
        min_health=0.0, max_health=0.3,
        compatible_modes=[FailureMode.OPEN_CIRCUIT],
        description="Open component's leads serve as quarter-wave antenna",
    ),
    RepurposeOption(
        application="Mechanical spacer / alignment",
        effectiveness=Effectiveness.LOW,
        min_health=0.0, max_health=0.1,
        compatible_modes=[FailureMode.OPEN_CIRCUIT, FailureMode.SHORT_CIRCUIT],
        description="Electrically dead component retains physical form factor",
    ),
    RepurposeOption(
        application="Adaptive LC filter",
        effectiveness=Effectiveness.MEDIUM,
        min_health=0.15, max_health=0.6,
        compatible_modes=[FailureMode.VALUE_DRIFT, FailureMode.ESR_RISE],
        description="Shifted L/C values create a filter at a new center frequency",
    ),
    RepurposeOption(
        application="OOK beacon shunt",
        effectiveness=Effectiveness.HIGH,
        min_health=0.0, max_health=0.4,
        compatible_modes=[FailureMode.SHORT_CIRCUIT],
        description="Shorted MOSFET/transistor acts as low-ohm keying switch",
    ),
]


# ---------------------------------------------------------------------------
# Router engine
# ---------------------------------------------------------------------------

class RepurposeRouter:
    """
    Score-and-gate decision engine.

    Scoring weights:
      - effectiveness:  40%  (High/Medium/Low intrinsic rating)
      - health_fit:     30%  (how well health falls in the option's sweet spot)
      - mode_match:     20%  (direct failure mode compatibility)
      - temp_penalty:   10%  (derating for extreme temperatures)
    """

    W_EFFECTIVENESS = 0.40
    W_HEALTH_FIT = 0.30
    W_MODE_MATCH = 0.20
    W_TEMP = 0.10

    def __init__(self, options: Optional[List[RepurposeOption]] = None):
        self.options = options or REPURPOSE_OPTIONS

    def route(self, health: ComponentHealth) -> List[RoutingResult]:
        results: List[RoutingResult] = []
        for opt in self.options:
            gate_pass, gate_reason = self._gate_check(health, opt)
            score = self._score(health, opt) if gate_pass else 0.0
            results.append(RoutingResult(
                option=opt, score=score, gate_pass=gate_pass,
                reasoning=gate_reason,
            ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def best(self, health: ComponentHealth) -> Optional[RoutingResult]:
        viable = [r for r in self.route(health) if r.gate_pass]
        return viable[0] if viable else None

    # -- internal --

    def _gate_check(self, health: ComponentHealth,
                    opt: RepurposeOption) -> Tuple[bool, str]:
        if health.failure_mode not in opt.compatible_modes:
            return False, f"Mode {health.failure_mode.value} incompatible"
        if health.health_score < opt.min_health:
            return False, f"Health {health.health_score:.2f} below min {opt.min_health}"
        if health.health_score > opt.max_health:
            return False, f"Health {health.health_score:.2f} above max {opt.max_health} (not degraded enough)"
        if opt.safety_critical and health.health_score < 0.5:
            return False, "Safety-critical application requires health >= 0.5"
        return True, "Pass"

    def _score(self, health: ComponentHealth,
               opt: RepurposeOption) -> float:
        eff = opt.effectiveness.score * self.W_EFFECTIVENESS

        midpoint = (opt.min_health + opt.max_health) / 2.0
        span = (opt.max_health - opt.min_health) / 2.0
        dist = abs(health.health_score - midpoint) / span if span > 0 else 0.0
        health_fit = (1.0 - dist) * self.W_HEALTH_FIT

        mode_match = self.W_MODE_MATCH  # already gated

        temp = health.temperature_c
        if temp > 85.0 or temp < -20.0:
            temp_score = 0.5 * self.W_TEMP
        elif temp > 60.0 or temp < 0.0:
            temp_score = 0.8 * self.W_TEMP
        else:
            temp_score = 1.0 * self.W_TEMP

        return eff + health_fit + mode_match + temp_score


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _print_results(label: str, health: ComponentHealth,
                   results: List[RoutingResult]) -> None:
    print(f"\n{'=' * 74}")
    print(f"  {label}")
    print(f"  Health: {health.health_score:.2f} | "
          f"Drift: {health.drift_pct:.1f}% | "
          f"Mode: {health.failure_mode.value} | "
          f"Temp: {health.temperature_c} deg C")
    print(f"{'=' * 74}")

    viable = [r for r in results if r.gate_pass]
    blocked = [r for r in results if not r.gate_pass]

    if viable:
        print(f"\n  Viable options ({len(viable)}):")
        print(f"  {'#':>3}  {'Score':>6}  {'Eff':>6}  Application")
        print(f"  {'---':>3}  {'------':>6}  {'------':>6}  {'-' * 40}")
        for i, r in enumerate(viable, 1):
            print(f"  {i:>3}  {r.score:>6.3f}  {r.option.effectiveness.value:>6}  "
                  f"{r.option.application}")
    else:
        print("\n  No viable repurpose options found.")

    if blocked:
        print(f"\n  Blocked ({len(blocked)}):")
        for r in blocked[:3]:
            print(f"    - {r.option.application}: {r.reasoning}")
        if len(blocked) > 3:
            print(f"    ... and {len(blocked) - 3} more")


def run() -> None:
    router = RepurposeRouter()

    scenarios: List[Tuple[str, ComponentHealth]] = [
        ("Resistor — moderate drift at high temp", ComponentHealth(
            component_type="resistor",
            failure_mode=FailureMode.VALUE_DRIFT,
            health_score=0.45, drift_pct=12.5, temperature_c=78.0,
        )),
        ("Diode — high leakage, partial degradation", ComponentHealth(
            component_type="diode",
            failure_mode=FailureMode.LEAKAGE_INCREASE,
            health_score=0.25, drift_pct=180.0, temperature_c=40.0,
        )),
        ("Capacitor — severe ESR rise", ComponentHealth(
            component_type="capacitor",
            failure_mode=FailureMode.ESR_RISE,
            health_score=0.15, drift_pct=85.0, temperature_c=55.0,
        )),
        ("MOSFET — shorted drain-source", ComponentHealth(
            component_type="transistor",
            failure_mode=FailureMode.SHORT_CIRCUIT,
            health_score=0.05, drift_pct=0.0, temperature_c=30.0,
        )),
        ("Inductor — open coil", ComponentHealth(
            component_type="inductor",
            failure_mode=FailureMode.OPEN_CIRCUIT,
            health_score=0.0, drift_pct=0.0, temperature_c=22.0,
        )),
        ("Transistor — gain degradation, noisy", ComponentHealth(
            component_type="transistor",
            failure_mode=FailureMode.GAIN_LOSS,
            health_score=0.35, drift_pct=60.0, temperature_c=35.0,
        )),
    ]

    print("Repurpose Decision Router Simulation")
    print(f"Knowledge base: {len(REPURPOSE_OPTIONS)} repurpose options loaded")

    for label, health in scenarios:
        results = router.route(health)
        _print_results(label, health, results)


if __name__ == "__main__":
    run()
