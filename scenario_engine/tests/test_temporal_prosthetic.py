"""Tests for the temporal prosthetic — single- and multi-process."""

import json
import multiprocessing
import os
import tempfile
import time
import unittest

from scenario_engine.temporal_prosthetic import (
    MarkerWriter,
    MarkerReader,
    TimeMarker,
    substrate_hash,
)


class SingleProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "markers.jsonl")
        self.writer = MarkerWriter("seq_a", self.path)
        self.reader = MarkerReader(self.writer)

    def tearDown(self):
        self.tmp.cleanup()

    def test_initial_state_empty(self):
        self.assertIsNone(self.reader.position())
        self.assertEqual(self.reader.length(), 0)

    def test_drop_marker_assigns_ordinals(self):
        for t in range(5):
            self.writer.drop_marker({"temp_c": 25.0 + t})
        self.assertEqual(self.reader.length(), 5)
        self.assertEqual(self.reader.position(), 4)
        ordinals = [m.ordinal for m in self.writer.sequence.markers]
        self.assertEqual(ordinals, [0, 1, 2, 3, 4])

    def test_substrate_hash_matches_state(self):
        m = self.writer.drop_marker({"temp_c": 65.0, "rate": 0.62})
        self.assertEqual(m.substrate_hash, substrate_hash({"temp_c": 65.0, "rate": 0.62}))

    def test_delta_from_prev(self):
        self.writer.drop_marker({"temp_c": 65.0})
        m1 = self.writer.drop_marker({"temp_c": 65.62})
        self.assertEqual(m1.delta_from_prev["temp_c"]["op"], "numeric")
        self.assertAlmostEqual(m1.delta_from_prev["temp_c"]["delta"], 0.62)

    def test_drift_signal_monotonic(self):
        for t in range(10):
            self.writer.drop_marker({"temp_c": 65.0 + t * 0.62})
        drift = self.reader.drift_signal(["temp_c"], n=10)
        self.assertEqual(drift["n"], 10)
        self.assertEqual(drift["monotonic_pct"], 1.0)
        self.assertAlmostEqual(drift["rate_per_step"], 0.62, places=5)

    def test_persistence_across_writers(self):
        for t in range(7):
            self.writer.drop_marker({"temp_c": 25.0 + t})
        w2 = MarkerWriter("seq_a", self.path)
        self.assertEqual(w2.length(), 7)
        self.assertEqual(w2.current_position(), 6)

    def test_tag_lookup(self):
        self.writer.drop_marker({"x": 1}, tags=["start"])
        self.writer.drop_marker({"x": 2}, tags=["intervened"])
        self.writer.drop_marker({"x": 3}, tags=["start", "anomaly"])
        starts = self.writer.find_by_tag("start")
        self.assertEqual([m.ordinal for m in starts], [0, 2])

    def test_look_back_until(self):
        for t in range(10):
            tags = ["above50"] if t >= 5 else []
            self.writer.drop_marker({"x": t}, tags=tags)
        walked = self.reader.look_back_until(lambda m: "above50" in m.tags)
        self.assertEqual([m.ordinal for m in walked], [5, 6, 7, 8, 9])

    def test_refresh_picks_up_external_appends(self):
        """If another process appends a marker, refresh() consumes it."""
        # Simulate: write a marker directly to the file as if from another process.
        external = {
            "sequence_id": "seq_a",
            "ordinal": 0,
            "wall_time": time.time(),
            "substrate_hash": "deadbeef",
            "state_summary": {"injected": True},
            "delta_from_prev": None,
            "claim_refs": [],
            "tags": ["external"],
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(external) + "\n")

        # Our writer doesn't know about it yet.
        self.assertEqual(self.reader.length(), 0)

        # Refresh pulls it in.
        added = self.reader.refresh()
        self.assertEqual(added, 1)
        self.assertEqual(self.reader.length(), 1)
        self.assertEqual(self.reader.look_back(1)[0].tags, ["external"])

    def test_multi_sequence_store_filters(self):
        """A shared store can hold multiple sequence_ids; each writer sees only its own."""
        writer_b = MarkerWriter("seq_b", self.path)
        self.writer.drop_marker({"x": 1})
        writer_b.drop_marker({"y": 100})
        self.writer.drop_marker({"x": 2})
        writer_b.drop_marker({"y": 200})

        self.reader.refresh()
        self.assertEqual(self.reader.length(), 2)
        self.assertEqual(writer_b.length(), 2)
        # Ordinals are independent per sequence_id.
        a_ords = [m.ordinal for m in self.writer.sequence.markers]
        b_ords = [m.ordinal for m in writer_b.sequence.markers]
        self.assertEqual(a_ords, [0, 1])
        self.assertEqual(b_ords, [0, 1])

    def test_partial_line_at_eof_is_tolerated(self):
        """Truncated final line shouldn't poison the cache; next refresh retries."""
        self.writer.drop_marker({"x": 1})
        with open(self.path, "a") as f:
            f.write('{"sequence_id":"seq_a","ordinal":99,')  # no newline, no closing brace
        # Refresh should leave length unchanged and not raise.
        self.assertEqual(self.reader.refresh(), 0)
        self.assertEqual(self.reader.length(), 1)


def _writer_worker(path: str, sequence_id: str, n: int, start_delay: float):
    """Subprocess body: drop N markers as fast as possible."""
    time.sleep(start_delay)  # let both processes hit the file roughly together
    w = MarkerWriter(sequence_id, path)
    for i in range(n):
        w.drop_marker({"pid": os.getpid(), "i": i})


class MultiProcessTests(unittest.TestCase):
    def test_two_processes_same_sequence_produce_monotonic_ordinals(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "shared.jsonl")

            ctx = multiprocessing.get_context("fork")
            p1 = ctx.Process(target=_writer_worker, args=(path, "shared", 50, 0.0))
            p2 = ctx.Process(target=_writer_worker, args=(path, "shared", 50, 0.0))
            p1.start()
            p2.start()
            p1.join(timeout=10)
            p2.join(timeout=10)
            self.assertEqual(p1.exitcode, 0)
            self.assertEqual(p2.exitcode, 0)

            # Read everything back through a fresh writer.
            w = MarkerWriter("shared", path)
            ordinals = [m.ordinal for m in w.sequence.markers]
            self.assertEqual(len(ordinals), 100)
            # Ordinals must be unique and strictly increasing.
            self.assertEqual(ordinals, sorted(ordinals))
            self.assertEqual(len(set(ordinals)), 100)
            self.assertEqual(ordinals[0], 0)
            self.assertEqual(ordinals[-1], 99)

            # Both PIDs must have contributed markers (concurrency really happened).
            pids = {m.state_summary["pid"] for m in w.sequence.markers}
            self.assertEqual(len(pids), 2)

    def test_two_processes_distinct_sequences_share_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "shared.jsonl")
            ctx = multiprocessing.get_context("fork")
            p1 = ctx.Process(target=_writer_worker, args=(path, "alpha", 30, 0.0))
            p2 = ctx.Process(target=_writer_worker, args=(path, "beta", 30, 0.0))
            p1.start()
            p2.start()
            p1.join(timeout=10)
            p2.join(timeout=10)
            self.assertEqual(p1.exitcode, 0)
            self.assertEqual(p2.exitcode, 0)

            w_alpha = MarkerWriter("alpha", path)
            w_beta = MarkerWriter("beta", path)
            self.assertEqual(w_alpha.length(), 30)
            self.assertEqual(w_beta.length(), 30)
            self.assertEqual(
                [m.ordinal for m in w_alpha.sequence.markers],
                list(range(30)),
            )
            self.assertEqual(
                [m.ordinal for m in w_beta.sequence.markers],
                list(range(30)),
            )


if __name__ == "__main__":
    unittest.main()
