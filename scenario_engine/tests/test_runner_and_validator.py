"""End-to-end: runner replays a scenario, validator grades claims against it."""

import os
import tempfile
import unittest

from scenario_engine.claims import ClaimWriter
from scenario_engine.runner import ScenarioRunner
from scenario_engine.scenarios.thermal_events import HeatSpikeLocalized
from scenario_engine.scenarios.power_events import VoltageSag
from scenario_engine.validators import OutcomeChecker


class RunnerArtifactTests(unittest.TestCase):
    def test_run_writes_state_and_outcome_files(self):
        with tempfile.TemporaryDirectory() as d:
            runner = ScenarioRunner(HeatSpikeLocalized(seed=3), write_dir=d)
            states = runner.run()
            self.assertGreater(len(states), 0)
            self.assertEqual(states[0].tick, 0)
            files = sorted(os.listdir(d))
            self.assertTrue(any(f.endswith(".state_stream.json") for f in files))
            self.assertTrue(any(f.endswith(".actual_outcome.json") for f in files))

    def test_state_machine_records_transitions(self):
        runner = ScenarioRunner(HeatSpikeLocalized(seed=3))
        runner.run()
        substrate = runner.machine.state
        self.assertEqual(substrate.system_state, "failed")
        self.assertIn("Q1", substrate.failed_components)
        # Expect at least one stable→degraded→failed transition.
        labels = [(t[1], t[2]) for t in substrate.transitions]
        self.assertTrue(any(to == "failed" for _, to in labels))


class OutcomeCheckerTests(unittest.TestCase):
    def _setup(self, scenario):
        with tempfile.TemporaryDirectory() as d:
            runner = ScenarioRunner(scenario, write_dir=d)
            runner.run()
            writer = ClaimWriter(os.path.join(d, "CLAIM_TABLE.substrate.json"))
            return runner, writer

    def test_correct_claim_validated(self):
        runner, writer = self._setup(HeatSpikeLocalized(seed=1))
        target = 150
        st = runner.state_at_tick(target)
        actual = st.actual_outcome["measurements"]["Q1_temp_c"]
        claim = writer.file_claim(
            tick=0, event_detected="x", decision="y", reasoning="z",
            prediction={
                f"Q1_temp_c_at_tick_{target}": actual,
                f"system_state_at_tick_{target}": "failed",
                "tolerance": 0.5,
            },
        )
        checker = OutcomeChecker(runner.states)
        v = checker.evaluate_one(claim)
        self.assertEqual(v.status, "VALIDATED")
        self.assertTrue(v.within_tolerance)

    def test_wrong_claim_invalidated(self):
        runner, writer = self._setup(HeatSpikeLocalized(seed=1))
        target = 150
        claim = writer.file_claim(
            tick=0, event_detected="x", decision="y", reasoning="z",
            prediction={
                f"Q1_temp_c_at_tick_{target}": -100.0,
                f"system_state_at_tick_{target}": "stable",
                "tolerance": 1.0,
            },
        )
        checker = OutcomeChecker(runner.states)
        v = checker.evaluate_one(claim)
        self.assertEqual(v.status, "INVALIDATED")

    def test_partial_claim_marked_partial(self):
        runner, writer = self._setup(HeatSpikeLocalized(seed=1))
        target = 150
        st = runner.state_at_tick(target)
        actual = st.actual_outcome["measurements"]["Q1_temp_c"]
        claim = writer.file_claim(
            tick=0, event_detected="x", decision="y", reasoning="z",
            prediction={
                f"Q1_temp_c_at_tick_{target}": actual,           # match
                f"system_state_at_tick_{target}": "stable",      # miss
                "tolerance": 0.5,
            },
        )
        checker = OutcomeChecker(runner.states)
        v = checker.evaluate_one(claim)
        self.assertEqual(v.status, "PARTIAL")

    def test_voltage_sag_does_not_fail_components(self):
        """False-positive rejection: VoltageSag has no permanent failure."""
        runner = ScenarioRunner(VoltageSag(seed=0))
        runner.run()
        substrate = runner.machine.state
        self.assertEqual(substrate.failed_components, [])
        self.assertIn(substrate.system_state, ("stable", "degraded"))


if __name__ == "__main__":
    unittest.main()
