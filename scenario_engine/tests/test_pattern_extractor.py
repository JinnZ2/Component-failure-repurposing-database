"""Tests for the feedback.pattern_extractor module.

Synthetic claim records cover each extractor function so the suite stays
deterministic and independent of any harness run.
"""

import json
import os
import tempfile
import unittest

from scenario_engine.continual_harness.feedback import (
    by_decision_accuracy,
    by_scenario_accuracy,
    db_effectiveness_audit,
    extract_all_patterns,
    numeric_error_distribution,
    recurring_failure_pattern,
    signed_bias_from_outcomes,
    systematic_bias,
)


def _claim(
    *,
    scenario="thermal_drift_localized",
    session="s1",
    decision="reroute_load_to_Q2",
    status="VALIDATED",
    prediction=None,
    validation=None,
    db_evidence=None,
):
    c = {
        "_scenario_name": scenario,
        "_session_id": session,
        "decision": decision,
        "status": status,
    }
    if prediction is not None:
        c["prediction"] = prediction
    if validation is not None:
        c["validation"] = validation
    if db_evidence is not None:
        c["db_evidence"] = db_evidence
    return c


class ByScenarioAccuracyTests(unittest.TestCase):
    def test_counts_and_accuracy(self):
        records = [
            _claim(scenario="A", status="VALIDATED"),
            _claim(scenario="A", status="VALIDATED"),
            _claim(scenario="A", status="INVALIDATED"),
            _claim(scenario="B", status="PARTIAL"),
        ]
        out = by_scenario_accuracy(records)
        self.assertEqual(out["A"]["validated"], 2)
        self.assertEqual(out["A"]["invalidated"], 1)
        self.assertAlmostEqual(out["A"]["accuracy"], 2 / 3, places=4)
        self.assertEqual(out["B"]["partial"], 1)

    def test_empty_returns_empty_dict(self):
        self.assertEqual(by_scenario_accuracy([]), {})


class ByDecisionAccuracyTests(unittest.TestCase):
    def test_groups_by_decision_string(self):
        records = [
            _claim(decision="reroute_to_spare", status="VALIDATED"),
            _claim(decision="reroute_to_spare", status="VALIDATED"),
            _claim(decision="reduce_load_50pct", status="INVALIDATED"),
        ]
        out = by_decision_accuracy(records)
        self.assertEqual(out["reroute_to_spare"]["total"], 2)
        self.assertEqual(out["reroute_to_spare"]["accuracy"], 1.0)
        self.assertEqual(out["reduce_load_50pct"]["accuracy"], 0.0)


class NumericErrorDistributionTests(unittest.TestCase):
    def test_extracts_max_error_per_claim(self):
        # _numeric_error now requires the underlying prediction to be numeric.
        # Categorical predictions (like 'system_state_at_tick_N') don't count
        # even though the validator records a 0.0/1.0 margin for them.
        records = [
            _claim(
                prediction={"Q1_temp_c_at_tick_50": 80.0, "x": 1.0},
                validation={"error_margins": {"Q1_temp_c_at_tick_50": 3.0, "x": 1.0}},
            ),
            _claim(
                prediction={"Q1_temp_c_at_tick_50": 80.0},
                validation={"error_margins": {"Q1_temp_c_at_tick_50": 7.0}},
            ),
            _claim(
                prediction={"y": 0.0},
                validation={"error_margins": {"y": 0.5}},
            ),
        ]
        dist = numeric_error_distribution(records)
        self.assertEqual(dist["n"], 3)
        self.assertEqual(dist["min"], 0.5)
        self.assertEqual(dist["max"], 7.0)
        self.assertAlmostEqual(dist["mean"], (3.0 + 7.0 + 0.5) / 3, places=4)

    def test_filters_categorical_margins(self):
        """system_state_at_tick_N stores 0.0/1.0 margins but is categorical."""
        records = [
            _claim(
                prediction={
                    "Q1_temp_c_at_tick_50": 80.0,
                    "system_state_at_tick_50": "stable",
                },
                validation={"error_margins": {
                    "Q1_temp_c_at_tick_50": 0.0,
                    "system_state_at_tick_50": 1.0,
                }},
            ),
        ]
        dist = numeric_error_distribution(records)
        # Only the numeric prediction's margin (0.0) counts, not the categorical 1.0.
        self.assertEqual(dist["max"], 0.0)

    def test_no_validation_returns_none(self):
        self.assertIsNone(numeric_error_distribution([_claim()]))


class SystematicBiasTests(unittest.TestCase):
    def test_temp_c_high_error_ratio(self):
        records = [
            _claim(
                prediction={"Q1_temp_c_at_tick_50": 30.0},
                validation={"error_margins": {"Q1_temp_c_at_tick_50": 6.0}},
            ),
            _claim(
                prediction={"Q1_temp_c_at_tick_50": 30.0},
                validation={"error_margins": {"Q1_temp_c_at_tick_50": 8.0}},
            ),
            _claim(
                prediction={"Q1_temp_c_at_tick_50": 30.0},
                validation={"error_margins": {"Q1_temp_c_at_tick_50": 1.0}},
            ),
        ]
        bias = systematic_bias(records, field_suffix="_temp_c")
        self.assertEqual(bias["samples"], 3)
        self.assertEqual(bias["high_error_count"], 2)
        self.assertAlmostEqual(bias["high_error_ratio"], 2 / 3, places=4)


class RecurringFailureTests(unittest.TestCase):
    def test_threshold_filters_low_occurrence(self):
        records = (
            [_claim(scenario="A", decision="d1", status="INVALIDATED")] * 5 +
            [_claim(scenario="A", decision="d2", status="INVALIDATED")] * 2
        )
        out = recurring_failure_pattern(records, min_occurrences=3)
        # d1 fails 5/5 → included; d2 only 2 → excluded
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["decision"], "d1")
        self.assertEqual(out[0]["failure_rate"], 1.0)

    def test_sorted_by_failure_rate(self):
        records = (
            [_claim(scenario="A", decision="d1", status="INVALIDATED")] * 3 +
            [_claim(scenario="A", decision="d1", status="VALIDATED")] * 3 +
            [_claim(scenario="A", decision="d2", status="INVALIDATED")] * 4
        )
        out = recurring_failure_pattern(records, min_occurrences=3)
        # d2 has higher failure_rate (1.0 vs 0.5)
        self.assertEqual(out[0]["decision"], "d2")
        self.assertEqual(out[1]["decision"], "d1")


class DBEffectivenessAuditTests(unittest.TestCase):
    def test_delta_signals_drift_between_claimed_and_observed(self):
        records = (
            [_claim(
                status="VALIDATED",
                db_evidence={"intervention": "reroute", "effectiveness_score": 0.9},
            )] * 6 +
            [_claim(
                status="INVALIDATED",
                db_evidence={"intervention": "reroute", "effectiveness_score": 0.9},
            )] * 4
        )
        audit = db_effectiveness_audit(records)
        self.assertEqual(len(audit), 1)
        e = audit[0]
        self.assertEqual(e["intervention"], "reroute")
        self.assertEqual(e["samples"], 10)
        self.assertAlmostEqual(e["observed_validation_rate"], 0.6, places=4)
        # DB claimed 0.9, observed 0.6 → delta -0.3
        self.assertAlmostEqual(e["delta"], -0.3, places=4)

    def test_skips_claims_without_db_evidence(self):
        self.assertEqual(db_effectiveness_audit([_claim()]), [])


class SignedBiasFromOutcomesTests(unittest.TestCase):
    def test_overprediction_flagged(self):
        # AI predicted 80 at tick 50; actual was 60 → signed err = +20
        records = [
            _claim(
                session="sA",
                prediction={"Q1_temp_c_at_tick_50": 80.0},
                validation={"error_margins": {"Q1_temp_c_at_tick_50": 20.0}},
            ),
            _claim(
                session="sA",
                prediction={"Q1_temp_c_at_tick_50": 90.0},
                validation={"error_margins": {"Q1_temp_c_at_tick_50": 30.0}},
            ),
        ]
        logs = {
            "sA": [
                {"tick": 50, "actual_outcome": {"Q1_temp_c": 60.0}},
            ],
        }
        bias = signed_bias_from_outcomes(records, state_logs_by_session=logs)
        self.assertIn("Q1_temp_c", bias)
        # mean_signed = ((80-60) + (90-60))/2 = 25.0
        self.assertAlmostEqual(bias["Q1_temp_c"]["mean_signed"], 25.0, places=4)
        self.assertTrue(bias["Q1_temp_c"]["all_overpredict"])
        self.assertFalse(bias["Q1_temp_c"]["all_underpredict"])

    def test_no_logs_returns_none(self):
        self.assertIsNone(
            signed_bias_from_outcomes([_claim()], state_logs_by_session=None)
        )


class ExtractAllPatternsTests(unittest.TestCase):
    def test_reads_history_writes_pattern_table(self):
        with tempfile.TemporaryDirectory() as d:
            history_path = os.path.join(d, "claim_history.json")
            with open(history_path, "w") as f:
                json.dump(
                    [
                        _claim(scenario="A", status="VALIDATED"),
                        _claim(scenario="A", status="INVALIDATED"),
                    ],
                    f,
                )
            out_path = os.path.join(d, "PATTERN_TABLE.json")
            report = extract_all_patterns(history_path, output_path=out_path)
            self.assertEqual(report["total_claims"], 2)
            self.assertIn("A", report["by_scenario"])
            self.assertTrue(os.path.exists(out_path))
            with open(out_path) as f:
                on_disk = json.load(f)
            self.assertEqual(on_disk["total_claims"], 2)

    def test_missing_history_returns_error_dict(self):
        report = extract_all_patterns("/no/such/file.json")
        self.assertIn("error", report)


if __name__ == "__main__":
    unittest.main()
