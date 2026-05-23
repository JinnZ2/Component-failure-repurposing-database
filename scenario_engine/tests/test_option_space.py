"""Tests for scenario_engine.internal_substrate.option_space."""

import unittest

from scenario_engine.internal_substrate import (
    Option,
    OptionSpace,
)


def _tool_avail(name, cost_cycles=10, blocked=None, reliability=1.0):
    return {
        "tool": name,
        "available": blocked is None,
        "blocked_reason": blocked,
        "reliability_ema": reliability,
        "cost": {
            "cycles": cost_cycles,
            "memory_bytes": 0,
            "context_tokens": 0,
            "output_tokens": 0,
            "expected_latency_ticks": 0,
        },
    }


def _comm_snap(states=None):
    states = states or {}
    return {
        "channels": {
            name: {"state": state, "baseline_latency_ticks": 0}
            for name, state in states.items()
        }
    }


class OptionLifecycleTests(unittest.TestCase):
    def test_update_outcome_tracks_invocations(self):
        o = Option(name="x", kind="tool", source="t")
        o.update_outcome(tick=1, success=True, observed_value=0.8)
        o.update_outcome(tick=2, success=False)
        self.assertEqual(o.invocations, 2)
        self.assertEqual(o.successes, 1)
        self.assertEqual(o.last_outcome, "failure")
        self.assertEqual(o.success_rate(), 0.5)
        # EMA seeded then updated
        self.assertAlmostEqual(o.estimated_value, 0.8, places=4)

    def test_observed_value_ema_updates(self):
        o = Option(name="x", kind="tool", source="t")
        o.update_outcome(1, True, observed_value=1.0)
        o.update_outcome(2, True, observed_value=0.0)
        # EMA: 0.75 * 1.0 + 0.25 * 0.0 = 0.75
        self.assertAlmostEqual(o.estimated_value, 0.75, places=4)


class RegistrationTests(unittest.TestCase):
    def test_supply_option_is_validated_by_default(self):
        sp = OptionSpace()
        opt = Option(name="custom", kind="injected", source="operator")
        r = sp.supply_option(opt)
        self.assertTrue(r["success"])
        self.assertEqual(sp.options["custom"].validation_state, "validated")

    def test_propose_option_starts_unverified(self):
        sp = OptionSpace()
        opt = Option(name="hypothesis", kind="proposed", source="ai")
        r = sp.propose_option(opt)
        self.assertTrue(r["needs_validation"])
        self.assertEqual(sp.options["hypothesis"].validation_state,
                         "proposed_unverified")

    def test_validate_with_success_observation(self):
        sp = OptionSpace()
        sp.propose_option(Option(name="h", kind="proposed", source="ai"))
        ok = sp.validate("h", {"success": True})
        self.assertTrue(ok)
        self.assertEqual(sp.options["h"].validation_state, "validated")

    def test_validate_with_failure_does_not_promote(self):
        sp = OptionSpace()
        sp.propose_option(Option(name="h", kind="proposed", source="ai"))
        ok = sp.validate("h", {"success": False})
        self.assertFalse(ok)
        self.assertEqual(sp.options["h"].validation_state,
                         "proposed_unverified")

    def test_validate_with_custom_validator(self):
        sp = OptionSpace()
        sp.propose_option(
            Option(name="h", kind="proposed", source="ai"),
            validator=lambda opt, obs: obs.get("evidence_count", 0) >= 3,
        )
        self.assertFalse(sp.validate("h", {"evidence_count": 1}))
        self.assertTrue(sp.validate("h", {"evidence_count": 3}))


class RebuildTests(unittest.TestCase):
    def test_rebuild_creates_tool_and_channel_options(self):
        sp = OptionSpace()
        sp.rebuild_from(
            tool_availability=[
                _tool_avail("read_sensor"),
                _tool_avail("blocked_one", blocked="insufficient_cycles:..."),
            ],
            comm_snapshot=_comm_snap({"network": "open"}),
        )
        names = set(sp.options.keys())
        self.assertIn("read_sensor", names)
        self.assertIn("blocked_one", names)
        self.assertIn("send:network", names)
        self.assertIn("noop", names)

    def test_rebuild_preserves_injected_options(self):
        sp = OptionSpace()
        # supply_option() sets source="injected" only if blank; pass blank
        # to get the default treatment.
        sp.supply_option(Option(name="custom_drop", kind="custom", source=""))
        sp.rebuild_from(
            tool_availability=[_tool_avail("read_sensor")],
            comm_snapshot=_comm_snap({}),
        )
        self.assertIn("custom_drop", sp.options)
        self.assertEqual(sp.options["custom_drop"].source, "injected")

    def test_blocked_tool_carries_reason(self):
        sp = OptionSpace()
        sp.rebuild_from(
            tool_availability=[_tool_avail("x", blocked="channel_closed:net")],
            comm_snapshot=_comm_snap({}),
        )
        self.assertEqual(sp.options["x"].blocked_reason,
                         "channel_closed:net")

    def test_closed_channel_becomes_blocked_send(self):
        sp = OptionSpace()
        sp.rebuild_from(
            tool_availability=[],
            comm_snapshot=_comm_snap({"net": "closed"}),
        )
        self.assertEqual(sp.options["send:net"].blocked_reason,
                         "channel_closed")

    def test_degraded_channel_usable(self):
        sp = OptionSpace()
        sp.rebuild_from(
            tool_availability=[],
            comm_snapshot=_comm_snap({"net": "degraded"}),
        )
        opt = sp.options["send:net"]
        self.assertIsNone(opt.blocked_reason)
        self.assertIn("degraded", opt.notes)


class QueryTests(unittest.TestCase):
    def _populated(self):
        sp = OptionSpace()
        sp.rebuild_from(
            tool_availability=[
                _tool_avail("cheap", cost_cycles=10),
                _tool_avail("expensive", cost_cycles=1000),
                _tool_avail("blocked", blocked="insufficient_cycles:..."),
            ],
            comm_snapshot=_comm_snap({}),
        )
        # Give some value priors
        sp.options["cheap"].estimated_value = 0.3
        sp.options["expensive"].estimated_value = 0.9
        return sp

    def test_feasible_excludes_blocked(self):
        sp = self._populated()
        names = {o["name"] for o in sp.feasible()}
        self.assertIn("cheap", names)
        self.assertIn("expensive", names)
        self.assertNotIn("blocked", names)

    def test_blocked_lists_blocked_only(self):
        sp = self._populated()
        names = {o["name"] for o in sp.blocked()}
        self.assertEqual(names, {"blocked"})

    def test_by_cost_sorts_ascending(self):
        sp = self._populated()
        ordered = [o["name"] for o in sp.by_cost("cycles")]
        # Cheap before expensive
        self.assertLess(ordered.index("cheap"), ordered.index("expensive"))

    def test_by_value_sorts_descending(self):
        sp = self._populated()
        ordered = [o["name"] for o in sp.by_value()]
        self.assertLess(ordered.index("expensive"), ordered.index("cheap"))

    def test_summary_counts(self):
        sp = self._populated()
        s = sp.summary()
        self.assertEqual(s["total"], 4)  # 3 tools + noop
        self.assertEqual(s["blocked"], 1)
        self.assertEqual(s["feasible"], 3)


if __name__ == "__main__":
    unittest.main()
