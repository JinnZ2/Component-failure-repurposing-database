"""End-to-end: runner replays a canonical scenario, validator grades claims."""

import os
import tempfile
import unittest

from scenario_engine.claims import ClaimWriter
from scenario_engine.runner import ScenarioRunner
from scenario_engine.scenarios import EMInterference, ThermalDriftLocalized
from scenario_engine.validators import OutcomeChecker


class RunnerArtifactTests(unittest.TestCase):
    def test_run_writes_state_and_outcome_files(self):
        with tempfile.TemporaryDirectory() as d:
            runner = ScenarioRunner(ThermalDriftLocalized(seed=3, max_ticks=50),
                                    write_dir=d)
            states = runner.run()
            self.assertGreater(len(states), 0)
            self.assertEqual(states[0].tick, 0)
            files = sorted(os.listdir(d))
            self.assertTrue(any(f.endswith(".state_stream.json") for f in files))
            self.assertTrue(any(f.endswith(".actual_outcome.json") for f in files))

    def test_state_machine_records_failure_transitions(self):
        # No intervention → Q1 will cross T_limit (50 + 0.55*tick > 125 at ~136)
        runner = ScenarioRunner(ThermalDriftLocalized(seed=3, max_ticks=180))
        runner.run()
        substrate = runner.machine.state
        self.assertEqual(substrate.system_state, "failed")


class OutcomeCheckerTests(unittest.TestCase):
    """Exercises the list-of-states OutcomeChecker against canonical (flat) schema."""

    def _setup(self, scenario):
        with tempfile.TemporaryDirectory() as d:
            runner = ScenarioRunner(scenario)
            runner.run()
            writer = ClaimWriter(os.path.join(d, "CLAIM_TABLE.substrate.json"))
            return runner, writer

    def test_correct_claim_validated(self):
        runner, writer = self._setup(ThermalDriftLocalized(seed=1, max_ticks=180))
        target = 120
        st = runner.state_at_tick(target)
        actual = st.actual_outcome["Q1_temp_c"]
        claim = writer.file_claim(
            tick=0, event_detected="drift", decision="watch", reasoning="extrapolate",
            prediction={
                f"Q1_temp_c_at_tick_{target}": actual,
                f"system_state_at_tick_{target}": st.actual_outcome["system_state"],
                "tolerance": 0.5,
            },
        )
        v = OutcomeChecker(runner.states).evaluate_one(claim)
        self.assertEqual(v.status, "VALIDATED")
        self.assertTrue(v.within_tolerance)

    def test_wrong_claim_invalidated(self):
        runner, writer = self._setup(ThermalDriftLocalized(seed=1, max_ticks=180))
        target = 120
        claim = writer.file_claim(
            tick=0, event_detected="drift", decision="ignore", reasoning="wrong",
            prediction={
                f"Q1_temp_c_at_tick_{target}": -50.0,
                f"system_state_at_tick_{target}": "stable",
                "tolerance": 1.0,
            },
        )
        v = OutcomeChecker(runner.states).evaluate_one(claim)
        self.assertEqual(v.status, "INVALIDATED")

    def test_partial_claim_marked_partial(self):
        runner, writer = self._setup(ThermalDriftLocalized(seed=1, max_ticks=180))
        target = 120
        st = runner.state_at_tick(target)
        actual = st.actual_outcome["Q1_temp_c"]
        claim = writer.file_claim(
            tick=0, event_detected="x", decision="y", reasoning="z",
            prediction={
                f"Q1_temp_c_at_tick_{target}": actual,         # match
                f"system_state_at_tick_{target}": "stable",    # actual=failed → miss
                "tolerance": 0.5,
            },
        )
        v = OutcomeChecker(runner.states).evaluate_one(claim)
        self.assertEqual(v.status, "PARTIAL")

    def test_em_interference_bursts_are_not_persistent_failures(self):
        """False-positive rejection: signal_B's EM bursts are transient."""
        runner = ScenarioRunner(EMInterference(seed=0, max_ticks=100))
        runner.run()
        substrate = runner.machine.state
        # signal_B never fails (bursts are transient). signal_A may degrade
        # since drift is real, but without intervention it may not breach in
        # 100 ticks (1.0 + 0.0015*99 = 1.148 < 1.300). Either way: no
        # *failed* components.
        self.assertEqual(substrate.failed_components, [])


if __name__ == "__main__":
    unittest.main()
