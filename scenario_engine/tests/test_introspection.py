"""Tests for scenario_engine.internal_substrate.introspection."""

import unittest

from scenario_engine.internal_substrate import (
    AIBody,
    Channel,
    ChannelState,
    CommChannels,
    IntrospectionReport,
    OptionSpace,
    SelfReport,
    TokenBudget,
    default_inventory,
)


def _build_report(
    channel_states=None,
    output_tokens_used=0,
    context_tokens_used=0,
) -> SelfReport:
    body = AIBody()
    tokens = TokenBudget()
    if output_tokens_used:
        tokens.spend_output(output_tokens_used)
    if context_tokens_used:
        tokens.add_to_context(context_tokens_used, tick=0)
    comms = CommChannels()
    channel_states = channel_states or {}
    for name, state in channel_states.items():
        comms.register(Channel(name, "out", bandwidth_bytes_per_tick=1024,
                               state=state))
    tools = default_inventory()
    options = OptionSpace()
    return SelfReport(body, tools, comms, tokens, options)


class HappyPathTests(unittest.TestCase):
    def test_full_returns_populated_report(self):
        sr = _build_report(channel_states={
            "sensor_bus": ChannelState.OPEN,
            "local":      ChannelState.OPEN,
            "network":    ChannelState.OPEN,
        })
        report = sr.full()
        self.assertIsInstance(report, IntrospectionReport)
        self.assertGreater(len(report.body), 0)
        self.assertGreater(len(report.tools), 0)
        self.assertGreater(len(report.channels), 0)
        self.assertGreater(len(report.tokens), 0)
        # cost paid > 0 from read_sensor
        self.assertGreater(report.cost_paid["cycles"], 0)

    def test_full_rebuilds_option_space(self):
        sr = _build_report(channel_states={
            "sensor_bus": ChannelState.OPEN,
            "local":      ChannelState.OPEN,
            "network":    ChannelState.OPEN,
        })
        report = sr.full(refresh_options=True)
        # All default tools should appear
        opt_names = {o["name"] for o in report.options["options"]}
        self.assertIn("read_sensor", opt_names)
        self.assertIn("emit_claim", opt_names)
        # Channel sends appear too
        self.assertIn("send:network", opt_names)


class WarningTests(unittest.TestCase):
    def test_channel_closed_warning(self):
        sr = _build_report(channel_states={
            "local": ChannelState.OPEN,
            "network": ChannelState.CLOSED,
        })
        report = sr.full()
        self.assertTrue(
            any("channels_closed" in w for w in report.warnings),
            report.warnings,
        )

    def test_channel_degraded_warning(self):
        sr = _build_report(channel_states={
            "local": ChannelState.OPEN,
            "network": ChannelState.DEGRADED,
        })
        report = sr.full()
        self.assertTrue(
            any("channels_degraded" in w for w in report.warnings),
            report.warnings,
        )

    def test_all_channels_closed_yields_no_open_channels_warning(self):
        sr = _build_report(channel_states={
            "local": ChannelState.CLOSED,
            "network": ChannelState.CLOSED,
        })
        report = sr.full()
        self.assertIn("no_open_channels", report.warnings)

    def test_no_warnings_in_nominal_state(self):
        sr = _build_report(channel_states={
            "sensor_bus": ChannelState.OPEN,
            "local":      ChannelState.OPEN,
            "network":    ChannelState.OPEN,
        })
        report = sr.full()
        # Should have no body/channel warnings — only possibly token
        # advisories at high context fill, but we didn't push tokens.
        self.assertFalse(
            any("body_throttled" in w or "channels_closed" in w
                or "no_open_channels" in w
                for w in report.warnings),
            report.warnings,
        )


class HeadroomTests(unittest.TestCase):
    def test_headroom_dimensions_present(self):
        sr = _build_report(channel_states={"local": ChannelState.OPEN})
        report = sr.full()
        h = report.headroom
        self.assertIn("cycles", h)
        self.assertIn("working_memory_bytes", h)
        self.assertIn("output_tokens", h)
        self.assertIn("context_tokens", h)
        self.assertEqual(h["open_channels"], 1)

    def test_headroom_reflects_token_spend(self):
        sr = _build_report(
            channel_states={"local": ChannelState.OPEN},
            output_tokens_used=500,
            context_tokens_used=1000,
        )
        report = sr.full()
        self.assertEqual(report.headroom["output_tokens"],
                         TokenBudget.DEFAULT_OUTPUT_PER_TICK - 500)
        self.assertEqual(report.headroom["context_tokens"],
                         TokenBudget.DEFAULT_CONTEXT_WINDOW - 1000)


class QuickWarningsTests(unittest.TestCase):
    def test_quick_warnings_does_not_pay(self):
        sr = _build_report(channel_states={"local": ChannelState.CLOSED})
        body_cycles_before = sr.body.compute.cycles_used_this_tick
        warnings = sr.quick_warnings()
        # No cycles spent: it's read-only
        self.assertEqual(sr.body.compute.cycles_used_this_tick,
                         body_cycles_before)
        self.assertTrue(any("channels_closed" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
