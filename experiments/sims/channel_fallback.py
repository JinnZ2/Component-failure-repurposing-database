"""
Channel Fallback Switching Simulation
=======================================
Simulates emergency communication channel degradation and automatic
failover across RF, optical, acoustic, thermal, magnetic, noise, and
mechanical channels.

Models each channel's bandwidth, range, and reliability as they degrade
over time, with an orchestrator that switches to the next viable channel
when the current one drops below threshold.

Glyph tags (per redundancy_glyphs.csv):
  RF:         radio link, beaconing, caution
  Optical:    emit, detect, torch
  Acoustic:   sound out, target, listen
  Magnetic:   magnetic, loop, coupled
  Thermal:    temperature, heat, slow
  Noise:      noise, entropy, detection
  Mechanical: hardware, vibration, geometry

Evidence tier: Theoretical

Reference:
  - matrices/redundancy_channels.csv
  - matrices/redundancy_effectiveness.csv
  - matrices/redundancy_decay.csv
  - implementations/circuit_examples/emergency_communication/
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class ChannelType(Enum):
    RF = "RF"
    OPTICAL = "Optical"
    ACOUSTIC = "Acoustic"
    MAGNETIC = "Magnetic"
    THERMAL = "Thermal"
    NOISE = "Noise"
    MECHANICAL = "Mechanical"


@dataclass
class ChannelSpec:
    channel_type: ChannelType
    glyphs: str
    max_bandwidth_bps: float
    max_range_m: float
    base_reliability: float     # 0.0 to 1.0
    power_draw_mw: float
    degradation_rate: float     # per-hour reliability loss


@dataclass
class ChannelState:
    spec: ChannelSpec
    reliability: float
    bandwidth_bps: float
    range_m: float
    active: bool
    hours_active: int = 0
    failure_events: int = 0


@dataclass
class OrchestratorEvent:
    hour: int
    event_type: str             # "switch", "degrade", "recover", "exhausted"
    from_channel: Optional[str]
    to_channel: Optional[str]
    detail: str


# ---------------------------------------------------------------------------
# Channel specifications (from redundancy_effectiveness.csv)
# ---------------------------------------------------------------------------

CHANNEL_SPECS: List[ChannelSpec] = [
    ChannelSpec(ChannelType.RF, "radio/beacon/caution",
                max_bandwidth_bps=1200, max_range_m=5000,
                base_reliability=0.92, power_draw_mw=150,
                degradation_rate=0.003),
    ChannelSpec(ChannelType.OPTICAL, "emit/detect/torch",
                max_bandwidth_bps=100, max_range_m=500,
                base_reliability=0.88, power_draw_mw=50,
                degradation_rate=0.004),
    ChannelSpec(ChannelType.ACOUSTIC, "sound/target/listen",
                max_bandwidth_bps=50, max_range_m=200,
                base_reliability=0.85, power_draw_mw=80,
                degradation_rate=0.002),
    ChannelSpec(ChannelType.MAGNETIC, "magnetic/loop/coupled",
                max_bandwidth_bps=20, max_range_m=5,
                base_reliability=0.95, power_draw_mw=30,
                degradation_rate=0.001),
    ChannelSpec(ChannelType.THERMAL, "temp/heat/slow",
                max_bandwidth_bps=0.1, max_range_m=0.5,
                base_reliability=0.80, power_draw_mw=200,
                degradation_rate=0.005),
    ChannelSpec(ChannelType.NOISE, "noise/entropy/detect",
                max_bandwidth_bps=5, max_range_m=50,
                base_reliability=0.70, power_draw_mw=20,
                degradation_rate=0.006),
    ChannelSpec(ChannelType.MECHANICAL, "hw/vibration/geometry",
                max_bandwidth_bps=2, max_range_m=10,
                base_reliability=0.90, power_draw_mw=100,
                degradation_rate=0.002),
]


# ---------------------------------------------------------------------------
# Channel model
# ---------------------------------------------------------------------------

class Channel:
    """Models a single communication channel with degradation."""

    MIN_RELIABILITY = 0.10

    def __init__(self, spec: ChannelSpec):
        self.spec = spec
        self.reliability = spec.base_reliability
        self.bandwidth = spec.max_bandwidth_bps
        self.range_m = spec.max_range_m
        self.hours_active = 0
        self.failure_events = 0

    def tick(self, rng: random.Random, stress: float = 1.0) -> None:
        """Advance one hour. stress > 1.0 accelerates degradation."""
        self.hours_active += 1
        loss = self.spec.degradation_rate * stress
        loss += rng.gauss(0, self.spec.degradation_rate * 0.3)
        self.reliability = max(self.MIN_RELIABILITY,
                               self.reliability - max(0, loss))

        # Proportional bandwidth/range degradation
        rel_ratio = self.reliability / self.spec.base_reliability
        self.bandwidth = self.spec.max_bandwidth_bps * rel_ratio
        self.range_m = self.spec.max_range_m * (rel_ratio ** 0.5)

        # Random acute failure events
        if rng.random() < 0.005 * stress:
            self.reliability *= 0.7
            self.failure_events += 1

    @property
    def viable(self) -> bool:
        return self.reliability > 0.25

    def state(self, active: bool) -> ChannelState:
        return ChannelState(
            spec=self.spec, reliability=self.reliability,
            bandwidth_bps=self.bandwidth, range_m=self.range_m,
            active=active, hours_active=self.hours_active,
            failure_events=self.failure_events,
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class FallbackOrchestrator:
    """
    Multi-channel failover orchestrator.

    Priority order: RF > Optical > Acoustic > Magnetic > Mechanical > Noise > Thermal

    Switches to the next viable channel when the active channel's
    reliability drops below the switch threshold. Logs all events.
    """

    SWITCH_THRESHOLD = 0.35
    PRIORITY = [
        ChannelType.RF, ChannelType.OPTICAL, ChannelType.ACOUSTIC,
        ChannelType.MAGNETIC, ChannelType.MECHANICAL,
        ChannelType.NOISE, ChannelType.THERMAL,
    ]

    def __init__(self, specs: Optional[List[ChannelSpec]] = None):
        specs = specs or CHANNEL_SPECS
        self.channels: Dict[ChannelType, Channel] = {
            s.channel_type: Channel(s) for s in specs
        }
        self.active: Optional[ChannelType] = self.PRIORITY[0]
        self.events: List[OrchestratorEvent] = []
        self.hour = 0

    def run(self, hours: int, stress: float = 1.0,
            seed: int = 42) -> List[OrchestratorEvent]:
        rng = random.Random(seed)
        self.events = []

        for h in range(1, hours + 1):
            self.hour = h

            # Degrade all channels (even inactive ones degrade slower)
            for ctype, chan in self.channels.items():
                s = stress if ctype == self.active else stress * 0.3
                chan.tick(rng, s)

            # Check active channel
            if self.active:
                active_chan = self.channels[self.active]
                if active_chan.reliability < self.SWITCH_THRESHOLD:
                    self._switch(h)

        return self.events

    def _switch(self, hour: int) -> None:
        old = self.active
        best = self._find_best()

        if best and best != old:
            self.events.append(OrchestratorEvent(
                hour=hour, event_type="switch",
                from_channel=old.value if old else None,
                to_channel=best.value,
                detail=(f"Reliability of {old.value} dropped to "
                        f"{self.channels[old].reliability:.2f}; "
                        f"switching to {best.value} "
                        f"({self.channels[best].reliability:.2f})"),
            ))
            self.active = best
        elif not best:
            self.events.append(OrchestratorEvent(
                hour=hour, event_type="exhausted",
                from_channel=old.value if old else None,
                to_channel=None,
                detail="All channels below viability threshold",
            ))
            self.active = None

    def _find_best(self) -> Optional[ChannelType]:
        viable = [(ct, ch) for ct, ch in self.channels.items() if ch.viable]
        if not viable:
            return None
        viable.sort(key=lambda x: (
            -x[1].reliability,
            self.PRIORITY.index(x[0]) if x[0] in self.PRIORITY else 99,
        ))
        return viable[0][0]

    def snapshot(self) -> List[ChannelState]:
        return [ch.state(active=(ct == self.active))
                for ct, ch in self.channels.items()]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _fmt_bps(bps: float) -> str:
    if bps >= 1000:
        return f"{bps / 1000:.1f} kbps"
    if bps >= 1:
        return f"{bps:.1f} bps"
    return f"{bps * 60:.1f} bpm"


def run() -> None:
    print("Channel Fallback Switching Simulation")
    print("=" * 74)

    orch = FallbackOrchestrator()

    print("\nInitial channel status:")
    print(f"  {'Channel':<12} {'Glyphs':<24} {'BW':>10} {'Range':>8} "
          f"{'Reliability':>12} {'Power':>8}")
    print(f"  {'-' * 12} {'-' * 24} {'-' * 10} {'-' * 8} {'-' * 12} {'-' * 8}")
    for cs in orch.snapshot():
        marker = " *" if cs.active else ""
        print(f"  {cs.spec.channel_type.value:<12} {cs.spec.glyphs:<24} "
              f"{_fmt_bps(cs.bandwidth_bps):>10} {cs.range_m:>7.1f}m "
              f"{cs.reliability:>11.2f} {cs.spec.power_draw_mw:>7.0f}mW{marker}")

    # Run with moderate stress for 2000 hours
    hours = 2000
    stress = 1.5
    print(f"\nSimulating {hours:,} hours at stress factor {stress}x ...")
    events = orch.run(hours, stress=stress, seed=77)

    # Event log
    print(f"\nEvents ({len(events)}):")
    print(f"  {'Hour':>6}  {'Type':<10}  Detail")
    print(f"  {'-' * 6}  {'-' * 10}  {'-' * 50}")
    for e in events:
        print(f"  {e.hour:>6}  {e.event_type:<10}  {e.detail}")

    # Final status
    print(f"\nFinal channel status (after {hours:,} hours):")
    print(f"  {'Channel':<12} {'BW':>10} {'Range':>8} {'Reliability':>12} "
          f"{'Hours':>6} {'Failures':>9} {'Status'}")
    print(f"  {'-' * 12} {'-' * 10} {'-' * 8} {'-' * 12} "
          f"{'-' * 6} {'-' * 9} {'-' * 10}")
    for cs in orch.snapshot():
        status = "ACTIVE" if cs.active else ("viable" if cs.reliability > 0.25 else "dead")
        print(f"  {cs.spec.channel_type.value:<12} "
              f"{_fmt_bps(cs.bandwidth_bps):>10} {cs.range_m:>7.1f}m "
              f"{cs.reliability:>11.2f} {cs.hours_active:>6} "
              f"{cs.failure_events:>9} {status}")

    if orch.active:
        active_ch = orch.channels[orch.active]
        print(f"\n  Current active channel: {orch.active.value} "
              f"(reliability {active_ch.reliability:.2f})")
    else:
        print("\n  WARNING: All channels exhausted. No communication possible.")

    # Summary
    switches = sum(1 for e in events if e.event_type == "switch")
    exhausted = any(e.event_type == "exhausted" for e in events)
    print(f"\n  Total channel switches: {switches}")
    print(f"  System exhausted: {'YES' if exhausted else 'No'}")

    total_power = sum(cs.spec.power_draw_mw for cs in orch.snapshot() if cs.active)
    print(f"  Current power draw: {total_power:.0f} mW")

    print(f"\n{'=' * 74}")
    print("  Orchestration: multi-modal switching and composition")
    print("  Policy: non-critical, low-power, legal bands")
    print(f"{'=' * 74}")


if __name__ == "__main__":
    run()
