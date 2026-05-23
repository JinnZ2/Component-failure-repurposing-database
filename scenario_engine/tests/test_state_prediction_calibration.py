"""Tests for state_prediction_calibration.

Exercises both the upstream `validation.errors` schema (string match /
'actual=' format) and our live `validator.error_margins` schema (float
margins + notes string).
"""

import unittest

from scenario_engine.continual_harness.feedback import (
    confusion_matrix,
    recommend_threshold_adjustment,
    state_accuracy,
    systematic_state_bias,
)


def _claim_upstream(predicted, actual, *, key="system_state_at_tick_50"):
    """Upstream schema: validation.errors[key] = 'match' or 'actual=X'."""
    if predicted == actual:
        err = "match"
    else:
        err = f"predicted={predicted} actual={actual}"
    return {
        "prediction": {key: predicted},
        "validation": {"errors": {key: err}},
        "status": "VALIDATED" if predicted == actual else "INVALIDATED",
    }


def _claim_live(predicted, actual, *, key="system_state_at_tick_50"):
    """Our live schema: validator.error_margins[key] = 0.0/1.0 + notes."""
    if predicted == actual:
        return {
            "prediction": {key: predicted},
            "validator": {
                "error_margins": {key: 0.0},
                "notes": "",
            },
            "status": "VALIDATED",
        }
    return {
        "prediction": {key: predicted},
        "validator": {
            "error_margins": {key: 1.0},
            "notes": f"{key}: actual='{actual}'",
        },
        "status": "INVALIDATED",
    }


class ConfusionMatrixTests(unittest.TestCase):
    def test_upstream_schema_matches(self):
        records = [
            _claim_upstream("stable", "stable"),
            _claim_upstream("stable", "stable"),
            _claim_upstream("stable", "degraded"),
            _claim_upstream("degraded", "failed"),
        ]
        m = confusion_matrix(records)
        self.assertEqual(m["stable"]["stable"], 2)
        self.assertEqual(m["stable"]["degraded"], 1)
        self.assertEqual(m["degraded"]["failed"], 1)

    def test_live_schema_matches(self):
        records = [
            _claim_live("stable", "stable"),
            _claim_live("stable", "degraded"),
            _claim_live("stable", "degraded"),
            _claim_live("degraded", "stable"),
        ]
        m = confusion_matrix(records)
        self.assertEqual(m["stable"]["stable"], 1)
        self.assertEqual(m["stable"]["degraded"], 2)
        self.assertEqual(m["degraded"]["stable"], 1)


class StateAccuracyTests(unittest.TestCase):
    def test_per_state_accuracy(self):
        records = [
            _claim_live("stable", "stable"),
            _claim_live("stable", "stable"),
            _claim_live("stable", "degraded"),
            _claim_live("degraded", "degraded"),
        ]
        acc = state_accuracy(records)
        self.assertAlmostEqual(acc["stable"]["accuracy"], 2 / 3, places=4)
        self.assertEqual(acc["degraded"]["accuracy"], 1.0)


class SystematicBiasTests(unittest.TestCase):
    def test_dominant_misprediction_pattern(self):
        # 7 of 10 mispredictions are stable→degraded
        records = (
            [_claim_live("stable", "stable")] * 3 +
            [_claim_live("stable", "degraded")] * 7 +
            [_claim_live("degraded", "failed")] * 1
        )
        bias = systematic_state_bias(records)
        self.assertIsNotNone(bias)
        self.assertEqual(bias["total_predictions"], 11)
        self.assertEqual(bias["total_mispredictions"], 8)
        # Top pattern: stable→degraded
        top = bias["patterns"][0]
        self.assertEqual(top["predicted"], "stable")
        self.assertEqual(top["actual"], "degraded")
        # 7/8 of mispredictions → ratio_of_mispredictions > 0.5
        self.assertGreater(top["ratio_of_mispredictions"], 0.5)
        # bias_direction string should mention it
        self.assertIsNotNone(bias["bias_direction"])
        self.assertIn("stable", bias["bias_direction"])
        self.assertIn("degraded", bias["bias_direction"])

    def test_no_predictions_returns_none(self):
        self.assertIsNone(systematic_state_bias([]))


class RecommendThresholdTests(unittest.TestCase):
    def _bias_with(self, predicted, actual):
        return {
            "total_predictions": 10,
            "total_mispredictions": 5,
            "overall_state_accuracy": 0.5,
            "patterns": [{
                "predicted": predicted,
                "actual": actual,
                "count": 5,
                "ratio_of_mispredictions": 1.0,
                "ratio_of_all_predictions": 0.5,
            }],
            "bias_direction": "test",
        }

    def test_stable_then_degraded_tightens(self):
        rec = recommend_threshold_adjustment(self._bias_with("stable", "degraded"))
        self.assertEqual(rec["direction"], "more_conservative")
        self.assertEqual(rec["action"], "tighten_stable_threshold")

    def test_degraded_then_stable_loosens(self):
        rec = recommend_threshold_adjustment(self._bias_with("degraded", "stable"))
        self.assertEqual(rec["direction"], "less_conservative")

    def test_stable_then_failed_aborts(self):
        rec = recommend_threshold_adjustment(self._bias_with("stable", "failed"))
        self.assertEqual(rec["direction"], "much_more_conservative")

    def test_no_patterns_returns_none(self):
        self.assertIsNone(recommend_threshold_adjustment({"patterns": []}))


if __name__ == "__main__":
    unittest.main()
