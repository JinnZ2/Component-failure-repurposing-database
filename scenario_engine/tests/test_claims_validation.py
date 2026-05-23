"""Falsifiability validator rejects non-falsifiable claims at write time."""

import os
import tempfile
import unittest

from scenario_engine.claims import ClaimRejected, ClaimWriter
from scenario_engine.claims.schema import is_falsifiable


class IsFalsifiableTests(unittest.TestCase):
    def test_numeric_with_tolerance_passes(self):
        self.assertTrue(is_falsifiable({
            "Q1_temp_c_at_tick_100": 85.0,
            "tolerance": 5.0,
        }))

    def test_numeric_without_tolerance_fails(self):
        self.assertFalse(is_falsifiable({
            "Q1_temp_c_at_tick_100": 85.0,
        }))

    def test_categorical_pass(self):
        self.assertTrue(is_falsifiable({
            "system_state_at_tick_50": "failed",
        }))

    def test_categorical_unknown_vocab_fails(self):
        self.assertFalse(is_falsifiable({
            "system_state_at_tick_50": "doomed",
        }))

    def test_no_target_keys_fails(self):
        self.assertFalse(is_falsifiable({"hot": True}))

    def test_empty_fails(self):
        self.assertFalse(is_falsifiable({}))

    def test_mixed_numeric_and_categorical(self):
        self.assertTrue(is_falsifiable({
            "Q1_temp_c_at_tick_100": 85.0,
            "system_state_at_tick_100": "failed",
            "tolerance": 1.0,
        }))


class ClaimWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "CLAIM_TABLE.substrate.json")

    def test_accepts_falsifiable_claim(self):
        w = ClaimWriter(self.path)
        c = w.file_claim(
            tick=10,
            event_detected="x",
            decision="route",
            reasoning="r",
            prediction={
                "Q1_temp_c_at_tick_100": 85.0,
                "tolerance": 2.0,
            },
        )
        self.assertEqual(c.status, "pending")
        self.assertTrue(c.falsifiable)
        self.assertTrue(c.claim_id.startswith("claim_"))

    def test_rejects_non_falsifiable_claim(self):
        w = ClaimWriter(self.path)
        with self.assertRaises(ClaimRejected):
            w.file_claim(
                tick=0,
                event_detected="x",
                decision="ignore",
                reasoning="vibes",
                prediction={"will_break_eventually": True},
            )

    def test_rejects_numeric_without_tolerance(self):
        w = ClaimWriter(self.path)
        with self.assertRaises(ClaimRejected):
            w.file_claim(
                tick=0,
                event_detected="x",
                decision="ignore",
                reasoning="r",
                prediction={"Q1_temp_c_at_tick_100": 85.0},
            )

    def test_id_persistence(self):
        w1 = ClaimWriter(self.path)
        w1.file_claim(
            tick=1, event_detected="a", decision="b", reasoning="c",
            prediction={"x_at_tick_2": 1.0, "tolerance": 0.1},
        )
        w2 = ClaimWriter(self.path)
        c = w2.file_claim(
            tick=1, event_detected="a", decision="b", reasoning="c",
            prediction={"x_at_tick_2": 1.0, "tolerance": 0.1},
        )
        self.assertEqual(c.claim_id, "claim_0002")


if __name__ == "__main__":
    unittest.main()
