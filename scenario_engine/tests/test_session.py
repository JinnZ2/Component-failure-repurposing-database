"""End-to-end session test: SustainedDrift + scripted decider + AIBody."""

import json
import os
import tempfile
import unittest

from scenario_engine.claims import ClaimTable
from scenario_engine.internal_substrate import AIBody
from scenario_engine.runner import OpInterface, Session
from scenario_engine.scenarios import REGISTRY, SustainedDrift
from scenario_engine.validators import validate_prediction


class RegistryTests(unittest.TestCase):
    def test_registry_contains_canonical_seven(self):
        # Canonical library: 7 scenarios.
        self.assertEqual(len(REGISTRY), 7)
        for name in (
            "thermal_drift_localized",
            "sustained_drift",
            "power_brownout",
            "vibration_resonance",
            "em_interference",
            "cascade_event",
            "slow_degradation_electrolytic",
        ):
            self.assertIn(name, REGISTRY)
        self.assertIs(REGISTRY["sustained_drift"], SustainedDrift)


class ClaimTableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "CLAIM_TABLE.substrate.json")

    def test_accepts_falsifiable(self):
        t = ClaimTable(self.path)
        r = t.write_claim({
            "tick": 5,
            "event_detected": "x",
            "decision": "y",
            "reasoning": "z",
            "prediction": {"Q1_temp_c_at_tick_50": 100.0, "tolerance": 1.0},
        })
        self.assertTrue(r["accepted"])
        self.assertEqual(len(t.claims), 1)

    def test_rejects_non_falsifiable(self):
        t = ClaimTable(self.path)
        r = t.write_claim({
            "tick": 0, "event_detected": "x", "decision": "y", "reasoning": "z",
            "prediction": {"will_break": True},
        })
        self.assertFalse(r["accepted"])
        self.assertIn("not falsifiable", r["reason"])

    def test_accuracy_summary(self):
        t = ClaimTable(self.path)
        for status in ("VALIDATED", "VALIDATED", "INVALIDATED", "PARTIAL", "pending"):
            r = t.write_claim({
                "tick": 0, "event_detected": "x", "decision": "y", "reasoning": "z",
                "prediction": {"x_at_tick_1": 1.0, "tolerance": 0.1},
            })
            cid = r["claim_id"]
            if status != "pending":
                t.update_status(cid, status, {"status": status})
        s = t.accuracy_summary()
        self.assertEqual(s["total_claims"], 5)
        self.assertEqual(s["validated"], 2)
        self.assertEqual(s["invalidated"], 1)
        self.assertEqual(s["partial"], 1)
        self.assertEqual(s["pending"], 1)
        self.assertEqual(s["graded"], 4)
        self.assertAlmostEqual(s["accuracy_validated_over_graded"], 0.5)


class ValidatePredictionTests(unittest.TestCase):
    def test_flat_actual_outcome(self):
        # SustainedDrift's actual_outcome schema: flat, no 'measurements'
        actual = {"system_state": "degraded", "Q1_temp_c": 87.3}
        claim = {
            "claim_id": "c1",
            "prediction": {
                "Q1_temp_c_at_tick_100": 88.0,
                "system_state_at_tick_100": "degraded",
                "tolerance": 2.0,
            },
        }
        v = validate_prediction(claim, actual)
        self.assertEqual(v["status"], "VALIDATED")
        self.assertTrue(v["within_tolerance"])

    def test_nested_actual_outcome(self):
        # Baseline scenarios' schema: 'measurements' sub-dict
        actual = {
            "system_state": "failed",
            "measurements": {"Q1_temp_c": 87.3},
        }
        claim = {
            "claim_id": "c2",
            "prediction": {
                "Q1_temp_c_at_tick_100": 88.0,
                "system_state_at_tick_100": "failed",
                "tolerance": 2.0,
            },
        }
        v = validate_prediction(claim, actual)
        self.assertEqual(v["status"], "VALIDATED")

    def test_partial(self):
        actual = {"system_state": "stable", "Q1_temp_c": 87.3}
        claim = {
            "claim_id": "c3",
            "prediction": {
                "Q1_temp_c_at_tick_100": 88.0,           # match
                "system_state_at_tick_100": "failed",    # miss
                "tolerance": 2.0,
            },
        }
        v = validate_prediction(claim, actual)
        self.assertEqual(v["status"], "PARTIAL")

    def test_no_targets_invalidates(self):
        v = validate_prediction({"claim_id": "c4", "prediction": {"x": True}}, {})
        self.assertEqual(v["status"], "INVALIDATED")


class SustainedDriftBehaviourTests(unittest.TestCase):
    def test_q1_temp_rises_over_ticks(self):
        s = SustainedDrift(seed=0, max_ticks=20)
        s.reset()
        states = [s.step() for _ in range(20)]
        t0 = states[0].actual_outcome["Q1_temp_c"]
        t19 = states[19].actual_outcome["Q1_temp_c"]
        self.assertGreater(t19, t0)

    def test_reroute_intervention_cools_q1(self):
        s = SustainedDrift(seed=0, max_ticks=80)
        s.reset()
        # Let Q1 drift for 30 ticks
        for _ in range(30):
            s.step()
        T_before = s.actual_outcome_for("Q1") if hasattr(s, "actual_outcome_for") else None
        peak = s.components_state["Q1"]
        s.receive_intervention("reroute_load_Q1_to_spare", s.tick)
        for _ in range(30):
            s.step()
        T_after = s._component_temp("Q1")
        # After rerouting, Q1 should cool below the peak it would have reached.
        no_reroute_T = peak["T0"] + peak["rate"] * (s.tick - peak["start_tick"])
        self.assertLess(T_after, no_reroute_T)


class SessionEndToEndTests(unittest.TestCase):
    """Decider files a correct prediction → VALIDATED via Session loop."""

    def test_session_runs_and_validates(self):
        with tempfile.TemporaryDirectory() as d:
            filed = {"count": 0}

            def decider(external, body, ops):
                # File one falsifiable prediction at tick 10.
                if external["tick"] != 10 or filed["count"] > 0:
                    # Spend a few cycles so body thermal/budget logic exercises
                    ops.read_sensor()
                    return None
                filed["count"] += 1
                ops.read_sensor()
                ops.query_component_db("Q1_BJT_NPN")
                # Q1 drifts at rate 0.62 from T0=65 starting at tick 0.
                # At tick 60: T = 65 + 0.62 * 60 = 102.2  (within float rounding)
                return {
                    "tick": 10,
                    "event_detected": "Q1_thermal_drift",
                    "decision": "watch",
                    "reasoning": "extrapolate at rate 0.62 C/tick",
                    "prediction": {
                        "Q1_temp_c_at_tick_60": 102.2,
                        "system_state_at_tick_60": "degraded",
                        "tolerance": 0.5,
                    },
                }

            session = Session(
                scenario_name="sustained_drift",
                ai_decide=decider,
                output_dir=d,
                seed=0,
                max_ticks=80,
                external_thermal_coupling=0.0,
            )
            summary = session.run()
            self.assertEqual(summary["validated"], 1)
            self.assertEqual(summary["pending"], 0)
            # Logs exist
            self.assertTrue(os.path.exists(os.path.join(d, "state_log.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(d, "body_log.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(d, "summary.json")))
            self.assertTrue(os.path.exists(os.path.join(d, "CLAIM_TABLE.substrate.json")))

    def test_session_unknown_scenario_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                Session(
                    scenario_name="nope",
                    ai_decide=lambda *a, **k: None,
                    output_dir=d,
                )

    def test_session_propagates_intervention(self):
        with tempfile.TemporaryDirectory() as d:
            def decider(external, body, ops):
                if external["tick"] != 5:
                    return None
                ops.read_sensor()
                return {
                    "tick": 5,
                    "event_detected": "Q1_drift",
                    "decision": "reroute_load_Q1_to_spare",
                    "reasoning": "preemptive",
                    "prediction": {
                        "Q1_temp_c_at_tick_60": 60.0,
                        "tolerance": 50.0,    # very loose; we only care intervention fires
                    },
                }
            session = Session(
                scenario_name="sustained_drift",
                ai_decide=decider,
                output_dir=d,
                seed=0,
                max_ticks=30,
            )
            session.run()
            iv = session.scenario.interventions_received
            self.assertTrue(any("reroute_load_Q1_to_spare" in a for a, _ in iv))


if __name__ == "__main__":
    unittest.main()
