"""Tests for scenario_engine.internal_substrate.token_budget."""

import unittest

from scenario_engine.internal_substrate import TokenBudget, TokenSnapshot


class BasicAffordanceTests(unittest.TestCase):
    def test_initial_state(self):
        b = TokenBudget()
        self.assertEqual(b.context_used, 0)
        self.assertEqual(b.output_used_this_tick, 0)
        self.assertEqual(b.pressure(), 0.0)

    def test_output_headroom_drains_with_spend(self):
        b = TokenBudget(output_per_tick=100)
        b.spend_output(30)
        self.assertEqual(b.output_headroom(), 70)
        b.spend_output(40)
        self.assertEqual(b.output_headroom(), 30)

    def test_cant_afford_above_budget(self):
        b = TokenBudget(output_per_tick=100)
        self.assertFalse(b.can_afford_output(200))
        self.assertTrue(b.can_afford_output(100))


class SpendOutputTests(unittest.TestCase):
    def test_success_decrements_headroom(self):
        b = TokenBudget(output_per_tick=200)
        r = b.spend_output(50)
        self.assertTrue(r["success"])
        self.assertEqual(r["tokens_spent"], 50)
        self.assertEqual(b.output_used_this_tick, 50)

    def test_failure_when_insufficient(self):
        b = TokenBudget(output_per_tick=100)
        b.spend_output(80)
        r = b.spend_output(50)
        self.assertFalse(r["success"])
        self.assertEqual(r["reason"], "insufficient_output_tokens")
        self.assertEqual(r["available"], 20)
        # Failed spend doesn't mutate the budget
        self.assertEqual(b.output_used_this_tick, 80)


class AddToContextTests(unittest.TestCase):
    def test_success_adds_entry(self):
        b = TokenBudget(context_window=1000)
        r = b.add_to_context(100, kind="claim", priority=0.5, tick=1)
        self.assertTrue(r["success"])
        self.assertEqual(b.context_used, 100)
        self.assertEqual(len(b._history_entries), 1)
        self.assertEqual(b._history_entries[0]["kind"], "claim")

    def test_failure_when_window_exhausted(self):
        b = TokenBudget(context_window=100)
        b.add_to_context(80, tick=0)
        r = b.add_to_context(50, tick=1)
        self.assertFalse(r["success"])
        self.assertEqual(r["reason"], "insufficient_context_window")
        # Failed add doesn't mutate the budget
        self.assertEqual(b.context_used, 80)
        self.assertEqual(len(b._history_entries), 1)

    def test_auto_id_when_omitted(self):
        b = TokenBudget()
        r = b.add_to_context(10, kind="obs", tick=3)
        self.assertTrue(r["entry_id"].startswith("obs_3_"))

    def test_explicit_id_preserved(self):
        b = TokenBudget()
        r = b.add_to_context(10, entry_id="my_id", tick=0)
        self.assertEqual(r["entry_id"], "my_id")


class PressureTests(unittest.TestCase):
    def test_pressure_is_used_over_total(self):
        b = TokenBudget(context_window=1000)
        b.add_to_context(750, tick=0)
        self.assertAlmostEqual(b.pressure(), 0.75, places=4)

    def test_pressure_warning_in_snapshot(self):
        b = TokenBudget(context_window=1000, pruning_threshold=0.5)
        b.add_to_context(600, tick=0)
        snap = b.snapshot()
        self.assertTrue(any("context_pressure" in w for w in snap.warnings))

    def test_output_low_warning(self):
        b = TokenBudget(output_per_tick=100)
        b.spend_output(95)
        snap = b.snapshot()
        self.assertIn("output_budget_low", snap.warnings)


class PruneTests(unittest.TestCase):
    def _populate(self, b, entries):
        for i, (tokens, prio, tick) in enumerate(entries):
            b.add_to_context(tokens, priority=prio, tick=tick,
                             entry_id=f"e{i}")
        return b

    def test_default_strategy_evicts_lowest_priority_first(self):
        b = TokenBudget(context_window=1000, pruning_threshold=0.8)
        self._populate(b, [
            (200, 0.9, 0),  # e0: high priority, old
            (200, 0.1, 1),  # e1: low priority, old
            (200, 0.5, 2),  # e2: mid priority
            (200, 0.1, 3),  # e3: low priority, newer
        ])
        # context_used = 800, target_used = 1000 * (0.8 - 0.1) = 700
        # need to free 100. Lowest-priority + oldest-first: e1.
        r = b.prune()
        self.assertEqual(r["evicted"], ["e1"])
        self.assertEqual(r["freed"], 200)

    def test_target_tokens_overrides_default(self):
        b = TokenBudget(context_window=1000)
        self._populate(b, [
            (100, 0.1, 0),
            (100, 0.2, 1),
            (100, 0.3, 2),
        ])
        r = b.prune(target_tokens=150)
        # Free at least 150; first eviction frees 100, then 100 more → 200
        self.assertGreaterEqual(r["freed"], 150)
        # 2 evictions covers 200
        self.assertEqual(len(r["evicted"]), 2)

    def test_no_pressure_no_op(self):
        b = TokenBudget(context_window=1000, pruning_threshold=0.8)
        b.add_to_context(100, tick=0)
        r = b.prune()
        self.assertEqual(r["freed"], 0)
        self.assertEqual(r["reason"], "no_pressure")

    def test_custom_strategy_used(self):
        b = TokenBudget(context_window=1000)
        self._populate(b, [
            (100, 0.9, 0),
            (100, 0.1, 1),
        ])
        # Strategy that evicts highest-priority first (anti-default)
        def aggressive(entries):
            ordered = sorted(entries, key=lambda e: -e["priority"])
            return [e["id"] for e in ordered]
        r = b.prune(strategy=aggressive, target_tokens=50)
        self.assertEqual(r["evicted"], ["e0"])

    def test_pressure_drops_after_prune(self):
        b = TokenBudget(context_window=1000, pruning_threshold=0.8)
        self._populate(b, [(900, 0.1, 0)])
        before = b.pressure()
        b.prune(target_tokens=500)
        self.assertLess(b.pressure(), before)


class TickAdvancementTests(unittest.TestCase):
    def test_advance_resets_output_only(self):
        b = TokenBudget(output_per_tick=100, context_window=1000)
        b.spend_output(50)
        b.add_to_context(200, tick=0)
        b.advance_tick()
        self.assertEqual(b.output_used_this_tick, 0)
        # Context persists across ticks
        self.assertEqual(b.context_used, 200)


class SnapshotTests(unittest.TestCase):
    def test_snapshot_returns_dataclass(self):
        b = TokenBudget(context_window=1000, output_per_tick=100)
        b.add_to_context(300, tick=0)
        b.spend_output(20)
        snap = b.snapshot()
        self.assertIsInstance(snap, TokenSnapshot)
        self.assertEqual(snap.context_used, 300)
        self.assertEqual(snap.output_used_this_tick, 20)
        self.assertEqual(snap.context_headroom, 700)

    def test_to_dict_is_serializable(self):
        import json
        b = TokenBudget()
        b.add_to_context(50, tick=0)
        json.dumps(b.to_dict())  # must not raise


if __name__ == "__main__":
    unittest.main()
