"""Tests for scenario_engine.internal_substrate.comm_channels."""

import unittest

from scenario_engine.internal_substrate import (
    Channel,
    ChannelState,
    CommChannels,
)


class ChannelSendTests(unittest.TestCase):
    def test_send_succeeds_within_bandwidth(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024)
        r = ch.send(512, tick=1)
        self.assertTrue(r["success"])
        self.assertEqual(ch.bytes_used_this_tick, 512)
        self.assertEqual(r["expected_arrival_tick"], 1)

    def test_send_fails_when_bandwidth_exceeded(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024)
        ch.send(800, tick=1)
        r = ch.send(500, tick=1)
        self.assertFalse(r["success"])
        self.assertEqual(r["reason"], "insufficient_bandwidth")
        self.assertEqual(r["available"], 224)

    def test_closed_channel_blocks_send(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024,
                     state=ChannelState.CLOSED)
        r = ch.send(100, tick=1)
        self.assertFalse(r["success"])
        self.assertEqual(r["reason"], "channel_closed")
        self.assertEqual(ch.last_failure_tick, 1)

    def test_in_only_channel_cannot_send(self):
        ch = Channel("c1", "in", bandwidth_bytes_per_tick=1024)
        self.assertFalse(ch.can_send(100))

    def test_latency_carried_in_arrival_tick(self):
        ch = Channel("c1", "bidi", bandwidth_bytes_per_tick=1024,
                     baseline_latency_ticks=3)
        r = ch.send(100, tick=10)
        self.assertEqual(r["expected_arrival_tick"], 13)


class ChannelReceiveTests(unittest.TestCase):
    def test_inbound_delivered_when_ready(self):
        ch = Channel("c1", "bidi", bandwidth_bytes_per_tick=1024)
        ch.inject_inbound({"id": "m1", "arrives_at": 5})
        ch.inject_inbound({"id": "m2", "arrives_at": 10})
        ready_at_5 = ch.receive(tick=5)
        self.assertEqual([m["id"] for m in ready_at_5], ["m1"])
        ready_at_10 = ch.receive(tick=10)
        self.assertEqual([m["id"] for m in ready_at_10], ["m2"])

    def test_corrupt_marked_in_event(self):
        ch = Channel("c1", "bidi", bandwidth_bytes_per_tick=1024)
        ch.inject_inbound({"id": "m1", "arrives_at": 0, "corrupt": True})
        ch.receive(tick=0)
        last = ch.history[-1]
        self.assertEqual(last.kind, "recv_corrupt")


class ObservationTests(unittest.TestCase):
    def test_latency_observation_updates_ema(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024,
                     baseline_latency_ticks=2)
        ch.observe({"latency_observed": 10}, tick=1)
        # First obs seeds baseline
        self.assertEqual(ch.degradation.latency_baseline_ticks, 10.0)
        # Drift = 10 - 2 baseline
        self.assertEqual(ch.degradation.latency_drift_ticks, 8.0)

        ch.observe({"latency_observed": 20}, tick=2)
        # EMA: 0.8 * 10 + 0.2 * 20 = 12
        self.assertAlmostEqual(ch.degradation.latency_baseline_ticks, 12.0, places=4)

    def test_corruption_count_increments(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024)
        ch.observe({"corrupted": True}, tick=1)
        ch.observe({"corrupted": True}, tick=2)
        self.assertEqual(ch.degradation.corruption_events, 2)

    def test_free_notes_recorded_with_tick(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024)
        ch.observe({"free_note": "weird burst at noon"}, tick=42)
        self.assertEqual(len(ch.degradation.notes), 1)
        self.assertIn("t42", ch.degradation.notes[0])

    def test_intermittent_pattern_set(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024)
        ch.observe({"intermittent_note": "drops every 7 ticks"}, tick=1)
        self.assertEqual(
            ch.degradation.intermittent_pattern, "drops every 7 ticks"
        )


class StateTransitionTests(unittest.TestCase):
    def test_state_change_logged(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024)
        ch.set_state(ChannelState.DEGRADED, tick=5, reason="latency drift")
        self.assertEqual(ch.state, ChannelState.DEGRADED)
        self.assertEqual(ch.last_state_change_tick, 5)
        last = ch.history[-1]
        self.assertEqual(last.kind, "state_change")
        self.assertEqual(last.payload["from"], "open")
        self.assertEqual(last.payload["to"], "degraded")

    def test_no_op_when_already_in_state(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024,
                     state=ChannelState.OPEN)
        history_before = len(ch.history)
        ch.set_state(ChannelState.OPEN, tick=1)
        self.assertEqual(len(ch.history), history_before)

    def test_reset_degradation_clears_profile(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024)
        ch.observe({"corrupted": True}, tick=1)
        ch.reset_degradation()
        self.assertEqual(ch.degradation.corruption_events, 0)


class TickAdvancementTests(unittest.TestCase):
    def test_bandwidth_resets_each_tick(self):
        ch = Channel("c1", "out", bandwidth_bytes_per_tick=1024)
        ch.send(500, tick=1)
        ch.advance_tick()
        self.assertEqual(ch.bytes_used_this_tick, 0)


class CommChannelsTests(unittest.TestCase):
    def setUp(self):
        self.cc = CommChannels()
        self.cc.register(Channel("a", "out", 1024))
        self.cc.register(Channel("b", "out", 1024, state=ChannelState.DEGRADED))
        self.cc.register(Channel("c", "out", 1024, state=ChannelState.CLOSED))

    def test_partition_by_state(self):
        self.assertEqual(self.cc.open_channels(), ["a"])
        self.assertEqual(self.cc.degraded_channels(), ["b"])
        self.assertEqual(self.cc.closed_channels(), ["c"])

    def test_advance_tick_resets_all_bandwidths(self):
        self.cc.get("a").send(100, tick=1)
        self.cc.advance_tick()
        self.assertEqual(self.cc.get("a").bytes_used_this_tick, 0)

    def test_summary_groups_counts(self):
        s = self.cc.summary()
        self.assertEqual(s["counts"], {"open": 1, "degraded": 1, "closed": 1})
        self.assertIn("a", s["channels"])


if __name__ == "__main__":
    unittest.main()
