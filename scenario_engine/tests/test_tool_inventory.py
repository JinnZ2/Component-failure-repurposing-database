"""Tests for scenario_engine.internal_substrate.tool_inventory."""

import unittest

from scenario_engine.internal_substrate import (
    Tool,
    ToolInventory,
    default_inventory,
)


def _body_snapshot(cycles_free=10000, mem_free=100000):
    return {
        "compute": {
            "cycles_per_tick": cycles_free + 0,
            "cycles_used_this_tick": 0,
        },
        "working_memory": {
            "capacity_bytes": mem_free + 0,
            "used_bytes": 0,
        },
    }


def _token_snapshot(out_free=2000, ctx_free=30000):
    return {
        "output_headroom": out_free,
        "context_headroom": ctx_free,
    }


def _comm_snapshot(states=None):
    states = states or {}
    return {
        "channels": {
            name: {"state": state, "baseline_latency_ticks": 0}
            for name, state in states.items()
        }
    }


class OutcomeTrackingTests(unittest.TestCase):
    def test_success_raises_reliability_ema(self):
        t = Tool("x", "", 1, 1, 1, 1, 0)
        t.update_outcome(tick=1, result="success")
        # EMA: 0.8 * 1.0 + 0.2 * 1.0 = 1.0 still
        self.assertEqual(t.reliability_ema, 1.0)
        self.assertEqual(t.n_success, 1)

    def test_error_drops_reliability(self):
        t = Tool("x", "", 1, 1, 1, 1, 0)
        t.update_outcome(tick=1, result="error", error_kind="timeout_inner")
        # EMA: 0.8 * 1.0 + 0.2 * 0.0 = 0.8
        self.assertAlmostEqual(t.reliability_ema, 0.8, places=4)
        self.assertEqual(t.n_error, 1)
        self.assertEqual(t.error_kinds["timeout_inner"], 1)

    def test_blocked_does_not_update_ema(self):
        t = Tool("x", "", 1, 1, 1, 1, 0)
        before = t.reliability_ema
        t.update_outcome(tick=1, result="blocked")
        # Blocked is not the tool's fault → EMA unchanged
        self.assertEqual(t.reliability_ema, before)
        self.assertEqual(t.n_blocked, 1)

    def test_distribution_breakdown(self):
        t = Tool("x", "", 1, 1, 1, 1, 0)
        t.update_outcome(1, "success")
        t.update_outcome(2, "success")
        t.update_outcome(3, "error", "boom")
        t.update_outcome(4, "timeout")
        d = t.distribution()
        self.assertEqual(d["n"], 4)
        self.assertEqual(d["success_rate"], 0.5)
        self.assertEqual(d["error_rate"], 0.25)
        self.assertEqual(d["timeout_rate"], 0.25)

    def test_outcome_history_capped(self):
        t = Tool("x", "", 1, 1, 1, 1, 0)
        for i in range(50):  # more than the 32-cap
            t.update_outcome(i, "success")
        self.assertEqual(len(t.outcome_history), 32)


class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.inv = ToolInventory()
        self.inv.add_tool(Tool(
            name="cheap_tool",
            description="",
            cost_cycles=10,
            cost_memory_bytes=64,
            cost_tokens=32,
            cost_output_tokens=8,
            expected_latency_ticks=0,
        ))
        self.inv.add_tool(Tool(
            name="needs_network",
            description="",
            cost_cycles=10,
            cost_memory_bytes=64,
            cost_tokens=32,
            cost_output_tokens=8,
            expected_latency_ticks=0,
            requires_channel="network",
        ))

    def test_all_available_when_budget_plentiful(self):
        avail = self.inv.available(
            _body_snapshot(),
            _comm_snapshot({"network": "open"}),
            _token_snapshot(),
        )
        names = {a["tool"]: a for a in avail}
        self.assertTrue(names["cheap_tool"]["available"])
        self.assertTrue(names["needs_network"]["available"])

    def test_closed_channel_blocks_dependent_tool(self):
        avail = self.inv.available(
            _body_snapshot(),
            _comm_snapshot({"network": "closed"}),
            _token_snapshot(),
        )
        names = {a["tool"]: a for a in avail}
        self.assertFalse(names["needs_network"]["available"])
        self.assertIn("channel_closed", names["needs_network"]["blocked_reason"])
        # Cheap tool unaffected
        self.assertTrue(names["cheap_tool"]["available"])

    def test_missing_channel_reported(self):
        avail = self.inv.available(
            _body_snapshot(),
            _comm_snapshot({}),  # network not registered
            _token_snapshot(),
        )
        names = {a["tool"]: a for a in avail}
        self.assertFalse(names["needs_network"]["available"])
        self.assertIn("channel_missing", names["needs_network"]["blocked_reason"])

    def test_insufficient_cycles_blocks(self):
        self.inv.add_tool(Tool(
            name="hog",
            description="",
            cost_cycles=10000,
            cost_memory_bytes=0,
            cost_tokens=0,
            cost_output_tokens=0,
            expected_latency_ticks=0,
        ))
        avail = self.inv.available(
            _body_snapshot(cycles_free=100),
            _comm_snapshot(),
            _token_snapshot(),
        )
        names = {a["tool"]: a for a in avail}
        self.assertFalse(names["hog"]["available"])
        self.assertIn("insufficient_cycles", names["hog"]["blocked_reason"])

    def test_insufficient_output_tokens_blocks(self):
        avail = self.inv.available(
            _body_snapshot(),
            _comm_snapshot({"network": "open"}),
            _token_snapshot(out_free=0),
        )
        names = {a["tool"]: a for a in avail}
        self.assertFalse(names["cheap_tool"]["available"])
        self.assertIn(
            "insufficient_output_tokens", names["cheap_tool"]["blocked_reason"]
        )


class DefaultInventoryTests(unittest.TestCase):
    def test_default_has_known_tools(self):
        inv = default_inventory()
        names = set(inv.tools.keys())
        self.assertIn("read_sensor", names)
        self.assertIn("emit_claim", names)
        self.assertIn("deep_analysis", names)
        self.assertIn("shallow_analysis", names)
        self.assertIn("introspect", names)


if __name__ == "__main__":
    unittest.main()
