"""
scenario_engine.internal_substrate.comm_channels

Communication channels the AI can use to send/receive.
Each channel has a state {open, degraded, closed} and a
DEGRADATION PROFILE the AI learns by observation.

The profile is NOT pre-specified. When a channel goes degraded,
the AI observes what's actually wrong (latency drift, bandwidth
drop, intermittent loss, corruption) and the profile fills in
from those observations.

This means two channels can both be "degraded" but behave very
differently. The AI must learn each one's signature.

Failure modes are not enumerated in advance. The AI discovers
them through use.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Deque
from collections import deque


class ChannelState(str, Enum):
    OPEN = "open"
    DEGRADED = "degraded"
    CLOSED = "closed"


@dataclass
class DegradationProfile:
    """
    AI-learned model of how a degraded channel behaves.
    Empty when channel is healthy. Populated from observations.

    All fields are running estimates updated by observation.
    Unknown fields stay None until the AI has data.
    """
    # Latency observations
    latency_baseline_ticks: Optional[float] = None
    latency_drift_ticks: Optional[float] = None
    latency_variance: Optional[float] = None

    # Bandwidth observations
    bandwidth_baseline_bps: Optional[float] = None
    bandwidth_drift_bps: Optional[float] = None

    # Reliability observations
    send_attempts: int = 0
    send_failures: int = 0
    corruption_events: int = 0
    intermittent_pattern: Optional[str] = None  # AI-supplied descriptor

    # Free-form observations the AI can store
    notes: List[str] = field(default_factory=list)

    def corruption_rate(self) -> float:
        if self.send_attempts == 0:
            return 0.0
        return self.corruption_events / self.send_attempts

    def failure_rate(self) -> float:
        if self.send_attempts == 0:
            return 0.0
        return self.send_failures / self.send_attempts


@dataclass
class ChannelEvent:
    tick: int
    kind: str  # "send_ok" | "send_fail" | "recv_ok" | "recv_corrupt" | "state_change"
    payload: Dict[str, Any] = field(default_factory=dict)


class Channel:
    """
    A single communication channel.

    The AI uses .send() / .receive() and observes the results.
    It calls .observe(...) to fold observations into the
    degradation profile. The channel doesn't infer for the AI.
    """

    def __init__(
        self,
        name: str,
        direction: str,                    # "in" | "out" | "bidi"
        bandwidth_bytes_per_tick: int,
        baseline_latency_ticks: int = 0,
        state: ChannelState = ChannelState.OPEN,
        history_capacity: int = 64,
    ):
        self.name = name
        self.direction = direction
        self.bandwidth_bytes_per_tick = bandwidth_bytes_per_tick
        self.baseline_latency_ticks = baseline_latency_ticks
        self.state = state
        self.bytes_used_this_tick = 0
        self.last_failure_tick: Optional[int] = None
        self.last_state_change_tick: int = 0
        self.degradation = DegradationProfile()
        self.history: Deque[ChannelEvent] = deque(maxlen=history_capacity)
        # Inbound queue for delayed deliveries (latency simulation)
        self._inbound: List[Dict[str, Any]] = []

    # ---- Capability checks ----------------------------------------------

    def can_send(self, byte_count: int) -> bool:
        if self.state == ChannelState.CLOSED:
            return False
        if self.direction == "in":
            return False
        return (self.bandwidth_bytes_per_tick - self.bytes_used_this_tick) >= byte_count

    def headroom_bytes(self) -> int:
        return max(0, self.bandwidth_bytes_per_tick - self.bytes_used_this_tick)

    # ---- Operations -----------------------------------------------------

    def send(
        self,
        byte_count: int,
        tick: int,
        payload_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.state == ChannelState.CLOSED:
            self._log(ChannelEvent(tick, "send_fail", {"reason": "closed"}))
            self.degradation.send_attempts += 1
            self.degradation.send_failures += 1
            self.last_failure_tick = tick
            return {"success": False, "reason": "channel_closed"}

        if not self.can_send(byte_count):
            self._log(
                ChannelEvent(tick, "send_fail", {"reason": "no_bandwidth"})
            )
            self.degradation.send_attempts += 1
            self.degradation.send_failures += 1
            return {
                "success": False,
                "reason": "insufficient_bandwidth",
                "available": self.headroom_bytes(),
            }

        self.bytes_used_this_tick += byte_count
        self.degradation.send_attempts += 1
        result = {
            "success": True,
            "bytes_sent": byte_count,
            "expected_arrival_tick": tick + self.baseline_latency_ticks,
            "payload_id": payload_id,
        }
        self._log(ChannelEvent(tick, "send_ok", {"bytes": byte_count}))
        return result

    def receive(self, tick: int) -> List[Dict[str, Any]]:
        ready = [m for m in self._inbound if m.get("arrives_at", 0) <= tick]
        self._inbound = [m for m in self._inbound if m.get("arrives_at", 0) > tick]
        for m in ready:
            kind = "recv_corrupt" if m.get("corrupt") else "recv_ok"
            self._log(ChannelEvent(tick, kind, {"id": m.get("id")}))
        return ready

    def inject_inbound(self, message: Dict[str, Any]):
        """External scenario / environment delivers a message here."""
        self._inbound.append(message)

    # ---- AI-driven observation ------------------------------------------

    def observe(self, observation: Dict[str, Any], tick: int):
        """
        AI folds an observation into the degradation profile.

        Expected keys (all optional):
          latency_observed:    int
          bandwidth_observed:  int
          corrupted:           bool
          intermittent_note:   str
          free_note:           str
        """
        d = self.degradation

        if "latency_observed" in observation:
            obs = float(observation["latency_observed"])
            if d.latency_baseline_ticks is None:
                d.latency_baseline_ticks = obs
            else:
                # EMA, alpha=0.2
                d.latency_baseline_ticks = (
                    0.8 * d.latency_baseline_ticks + 0.2 * obs
                )
            drift = obs - self.baseline_latency_ticks
            d.latency_drift_ticks = (
                drift if d.latency_drift_ticks is None
                else 0.8 * d.latency_drift_ticks + 0.2 * drift
            )

        if "bandwidth_observed" in observation:
            obs = float(observation["bandwidth_observed"])
            d.bandwidth_baseline_bps = (
                obs if d.bandwidth_baseline_bps is None
                else 0.8 * d.bandwidth_baseline_bps + 0.2 * obs
            )
            d.bandwidth_drift_bps = (
                obs - self.bandwidth_bytes_per_tick
            )

        if observation.get("corrupted"):
            d.corruption_events += 1
            self._log(ChannelEvent(tick, "recv_corrupt", {}))

        if "intermittent_note" in observation:
            d.intermittent_pattern = observation["intermittent_note"]

        if "free_note" in observation:
            d.notes.append(f"t{tick}: {observation['free_note']}")

    # ---- State transitions ----------------------------------------------

    def set_state(self, new_state: ChannelState, tick: int, reason: str = ""):
        if new_state == self.state:
            return
        self._log(
            ChannelEvent(
                tick,
                "state_change",
                {"from": self.state.value, "to": new_state.value, "reason": reason},
            )
        )
        self.state = new_state
        self.last_state_change_tick = tick
        if new_state == ChannelState.OPEN:
            # Reset degradation profile on recovery? AI-policy decision.
            # We keep the history; AI can clear it if desired.
            pass

    def reset_degradation(self):
        self.degradation = DegradationProfile()

    # ---- Tick advancement -----------------------------------------------

    def advance_tick(self):
        self.bytes_used_this_tick = 0

    # ---- Snapshot -------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "direction": self.direction,
            "state": self.state.value,
            "bandwidth_bytes_per_tick": self.bandwidth_bytes_per_tick,
            "bytes_used_this_tick": self.bytes_used_this_tick,
            "headroom_bytes": self.headroom_bytes(),
            "baseline_latency_ticks": self.baseline_latency_ticks,
            "last_failure_tick": self.last_failure_tick,
            "last_state_change_tick": self.last_state_change_tick,
            "degradation": asdict(self.degradation),
            "history_len": len(self.history),
            "inbound_queued": len(self._inbound),
        }

    # ---- Internals ------------------------------------------------------

    def _log(self, event: ChannelEvent):
        self.history.append(event)


class CommChannels:
    """Registry + tick coordinator for all channels."""

    def __init__(self):
        self.channels: Dict[str, Channel] = {}

    def register(self, channel: Channel):
        self.channels[channel.name] = channel

    def get(self, name: str) -> Optional[Channel]:
        return self.channels.get(name)

    def advance_tick(self):
        for ch in self.channels.values():
            ch.advance_tick()

    def open_channels(self) -> List[str]:
        return [
            name for name, c in self.channels.items()
            if c.state == ChannelState.OPEN
        ]

    def degraded_channels(self) -> List[str]:
        return [
            name for name, c in self.channels.items()
            if c.state == ChannelState.DEGRADED
        ]

    def closed_channels(self) -> List[str]:
        return [
            name for name, c in self.channels.items()
            if c.state == ChannelState.CLOSED
        ]

    def summary(self) -> Dict[str, Any]:
        return {
            "channels": {
                name: ch.snapshot() for name, ch in self.channels.items()
            },
            "counts": {
                "open": len(self.open_channels()),
                "degraded": len(self.degraded_channels()),
                "closed": len(self.closed_channels()),
            },
        }
