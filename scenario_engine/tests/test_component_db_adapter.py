"""Tests for the component_db_adapter package.

Uses inline CSV fixtures rather than depending on the live matrices/
directory so the tests stay deterministic and the project's CSV data
is free to evolve.
"""

import os
import tempfile
import unittest

from scenario_engine.component_db_adapter import (
    ComponentDB,
    ComponentDBAdapter,
    EFFECTIVENESS_SCORE,
    load_all_matrices,
    load_csv,
)


def _write(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _fixture_dir(tmp: str):
    """Write a minimal four-matrix fixture set into tmp/."""
    _write(
        os.path.join(tmp, "failure_mode_matrix.csv"),
        "Component,Failure Mode,Repurpose Option,Effectiveness,Notes\n"
        "BJT_NPN,thermal_runaway,Temperature Sensor,High,Use Vbe drift\n"
        "BJT_NPN,thermal_runaway,Crude Heater,Low,Last resort\n"
        "BJT_NPN,open,Mechanical Spacer,Medium,Body still solid\n"
        "Resistor,Value Drift,Temperature Sensor,Medium,TCR usable\n",
    )
    _write(
        os.path.join(tmp, "repurpose_effectiveness.csv"),
        "Component,Failure Mode,Repurpose Application,Effectiveness,Notes\n"
        "Resistor,Open,Mechanical Spacer,High,Body intact\n"
        "Resistor,Value Drift,Temperature Sensor,Medium,Calibrated TCR\n",
    )
    _write(
        os.path.join(tmp, "environmental_interactions.csv"),
        "Component,Condition,Observed Effect,Repurpose Impact,Notes\n"
        "Capacitor,High Humidity (>70%),ESR drift accelerated,Worse for filter use,Try as sensor\n"
        "Capacitor,Thermal cycling,Capacitance drift,Less useful as storage,OK as heater\n"
        "BJT_NPN,Vibration,Solder joint stress,Mounting must dampen,Add foam\n",
    )
    _write(
        os.path.join(tmp, "component_synergies.csv"),
        "Component A,Component B,Synergy Effect,Repurpose Application,Notes\n"
        "Diode (Shorted),Resistor (Value Drift),Temp coeff + R drift,Distributed thermal sensing,Combine readings\n"
        "BJT_NPN (Failed),Capacitor (ESR high),Junction stability + ESR signature,Anomaly detector,Pair on shared rail\n",
    )


class CsvLoaderTests(unittest.TestCase):
    def test_load_csv_snake_case_headers(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f.csv")
            _write(path, "Component,Failure Mode\nQ1,thermal_runaway\n")
            rows = load_csv(path)
            self.assertEqual(rows, [{"component": "Q1", "failure_mode": "thermal_runaway"}])

    def test_load_csv_attaches_effectiveness_score(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f.csv")
            _write(
                path,
                "Component,Effectiveness\nQ1,High\nQ2,Medium\nQ3,Low\nQ4,\n",
            )
            rows = load_csv(path)
            scores = [r["effectiveness_score"] for r in rows]
            self.assertEqual(scores, [0.9, 0.6, 0.3, 0.0])

    def test_load_csv_missing_file_returns_empty(self):
        self.assertEqual(load_csv("/no/such/file.csv"), [])

    def test_load_csv_strips_whitespace(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f.csv")
            _write(path, "Component,Notes\n  Q1  ,  ok  \n")
            rows = load_csv(path)
            self.assertEqual(rows[0], {"component": "Q1", "notes": "ok"})

    def test_load_all_matrices_known_schemas(self):
        with tempfile.TemporaryDirectory() as d:
            _fixture_dir(d)
            all_m = load_all_matrices(d)
            self.assertEqual(set(all_m.keys()), {
                "failure_mode_matrix",
                "repurpose_effectiveness",
                "environmental_interactions",
                "component_synergies",
            })
            self.assertEqual(len(all_m["failure_mode_matrix"]), 4)
            self.assertEqual(len(all_m["component_synergies"]), 2)

    def test_load_all_matrices_missing_yields_empty_list(self):
        with tempfile.TemporaryDirectory() as d:
            all_m = load_all_matrices(d)
            self.assertEqual(all_m["failure_mode_matrix"], [])
            self.assertEqual(all_m["component_synergies"], [])

    def test_effectiveness_score_table_constants(self):
        self.assertEqual(EFFECTIVENESS_SCORE["High"], 0.9)
        self.assertEqual(EFFECTIVENESS_SCORE["Medium"], 0.6)
        self.assertEqual(EFFECTIVENESS_SCORE["Low"], 0.3)


class ComponentDBTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        _fixture_dir(self.tmp.name)
        self.db = ComponentDB(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_summary(self):
        s = self.db.summary()
        self.assertEqual(s["failure_mode_matrix"], 4)
        self.assertEqual(s["component_synergies"], 2)

    def test_repurpose_options_ranked(self):
        opts = self.db.repurpose_options("BJT_NPN")
        self.assertEqual(len(opts), 3)
        scores = [o["effectiveness_score"] for o in opts]
        self.assertEqual(scores, sorted(scores, reverse=True))
        # All have _source for show-your-work
        for o in opts:
            self.assertEqual(o["_source"], "failure_mode_matrix")

    def test_repurpose_options_filter_by_mode(self):
        opts = self.db.repurpose_options("BJT_NPN", failure_mode="thermal_runaway")
        modes = {o["failure_mode"] for o in opts}
        self.assertEqual(modes, {"thermal_runaway"})
        self.assertEqual(len(opts), 2)

    def test_repurpose_options_case_insensitive(self):
        self.assertEqual(
            len(self.db.repurpose_options("bjt_npn")),
            len(self.db.repurpose_options("BJT_NPN")),
        )

    def test_best_intervention_picks_highest_effectiveness(self):
        best = self.db.best_intervention("BJT_NPN", "thermal_runaway")
        self.assertEqual(best["repurpose_option"], "Temperature Sensor")
        self.assertEqual(best["effectiveness"], "High")

    def test_best_intervention_returns_none_when_no_match(self):
        self.assertIsNone(self.db.best_intervention("Unobtainium", "any"))

    def test_repurpose_applications(self):
        apps = self.db.repurpose_applications("Resistor")
        self.assertEqual(len(apps), 2)
        # Sorted desc
        scores = [a["effectiveness_score"] for a in apps]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_environmental_factors(self):
        envs = self.db.environmental_factors("Capacitor")
        self.assertEqual(len(envs), 2)
        # Substring filter on condition
        humid = self.db.environmental_factors("Capacitor", condition="humidity")
        self.assertEqual(len(humid), 1)
        self.assertIn("Humidity", humid[0]["condition"])

    def test_synergies_filter_substring_match(self):
        # 'Diode' appears in 'Diode (Shorted)'
        syn = self.db.synergies("Diode")
        self.assertEqual(len(syn), 1)
        self.assertIn("Diode", syn[0]["component_a"])

    def test_synergies_all_when_no_filter(self):
        self.assertEqual(len(self.db.synergies()), 2)

    def test_reload_picks_up_csv_changes(self):
        before = self.db.summary()["failure_mode_matrix"]
        # Append a row to the CSV
        with open(os.path.join(self.tmp.name, "failure_mode_matrix.csv"), "a") as f:
            f.write("BJT_NPN,leakage,Sensitive Detector,High,Useful\n")
        # Before reload: stale
        self.assertEqual(self.db.summary()["failure_mode_matrix"], before)
        # After reload: fresh
        self.db.reload()
        self.assertEqual(self.db.summary()["failure_mode_matrix"], before + 1)


class _FakeOpInterface:
    """Minimal stand-in matching the OpInterface surface we care about."""

    def __init__(self, succeed: bool = True, cache_hit: bool = False):
        self._succeed = succeed
        self._cache_hit = cache_hit
        self.calls = []
        self.released = []

    def query_component_db(self, cache_key: str):
        self.calls.append(("query_component_db", cache_key))
        return {
            "success": self._succeed,
            "cycles_used": 20 if self._cache_hit else 500,
            "memory_used": 0 if self._cache_hit else 2048,
            "cache_hit": self._cache_hit,
        }

    def deep_analysis(self):
        self.calls.append(("deep_analysis",))
        return {"success": True}

    def release_memory(self, region: str, n_bytes: int):
        self.released.append((region, n_bytes))


class ComponentDBAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        _fixture_dir(self.tmp.name)
        self.adapter = ComponentDBAdapter(matrices_dir=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_constructor_uses_bundled_sample_data(self):
        """Default ComponentDBAdapter() finds bundled sample_data/ and loads it."""
        adapter = ComponentDBAdapter()
        # Bundled CSVs should yield non-empty matrices.
        s = adapter.db.summary()
        self.assertGreater(s["failure_mode_matrix"], 0)
        self.assertGreater(s["component_synergies"], 0)

    def test_missing_dir_raises(self):
        with self.assertRaises(ValueError):
            ComponentDBAdapter(matrices_dir="/no/such/directory")

    def test_wrap_delegates_other_methods(self):
        fake = _FakeOpInterface()
        wrapped = self.adapter.wrap(fake)
        wrapped.deep_analysis()
        wrapped.release_memory("working", 1024)
        self.assertIn(("deep_analysis",), fake.calls)
        self.assertEqual(fake.released, [("working", 1024)])

    def test_query_returns_cost_and_db_data(self):
        fake = _FakeOpInterface(succeed=True)
        wrapped = self.adapter.wrap(fake)
        result = wrapped.query_component_db(
            "BJT_NPN:thermal_runaway",
            component_type="BJT_NPN",
            failure_mode="thermal_runaway",
        )
        # Cost fields preserved from underlying op
        self.assertTrue(result["success"])
        self.assertEqual(result["cycles_used"], 500)
        # DB augmentation present
        self.assertIn("db", result)
        self.assertEqual(result["db"]["queried_component"], "BJT_NPN")
        self.assertEqual(result["db"]["queried_failure_mode"], "thermal_runaway")
        # Best should be the High-effectiveness Temperature Sensor option
        self.assertEqual(result["db"]["best"]["repurpose_option"], "Temperature Sensor")
        # repurpose_options is sorted desc
        scores = [o["effectiveness_score"] for o in result["db"]["repurpose_options"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_query_returns_none_db_when_cost_fails(self):
        fake = _FakeOpInterface(succeed=False)
        wrapped = self.adapter.wrap(fake)
        result = wrapped.query_component_db(
            "k", component_type="BJT_NPN", failure_mode="thermal_runaway"
        )
        self.assertFalse(result["success"])
        self.assertIsNone(result["db"])

    def test_query_without_component_type_warns(self):
        fake = _FakeOpInterface()
        wrapped = self.adapter.wrap(fake)
        result = wrapped.query_component_db("k")
        self.assertIn("warning", result["db"])

    def test_include_filter_controls_returned_sections(self):
        fake = _FakeOpInterface()
        wrapped = self.adapter.wrap(fake)
        result = wrapped.query_component_db(
            "k",
            component_type="BJT_NPN",
            failure_mode="thermal_runaway",
            include=["environmental", "synergies"],
        )
        # Only the requested sections appear; the default ones do not.
        self.assertIn("environmental", result["db"])
        self.assertIn("synergies", result["db"])
        self.assertNotIn("repurpose_options", result["db"])
        self.assertNotIn("best", result["db"])

    def test_best_is_none_when_failure_mode_missing(self):
        fake = _FakeOpInterface()
        wrapped = self.adapter.wrap(fake)
        result = wrapped.query_component_db(
            "k",
            component_type="BJT_NPN",
            failure_mode=None,
            include=["best"],
        )
        self.assertIsNone(result["db"]["best"])

    def test_underlying_op_called_with_cache_key(self):
        fake = _FakeOpInterface()
        wrapped = self.adapter.wrap(fake)
        wrapped.query_component_db("Q1:therm", component_type="BJT_NPN")
        self.assertEqual(fake.calls, [("query_component_db", "Q1:therm")])


class SessionWireInTests(unittest.TestCase):
    """Session passes the wrapped op_iface to the decider when db_adapter is set."""

    def test_decider_receives_db_augmented_op(self):
        from scenario_engine.runner import Session
        observed = {"saw_db": False, "best_repurpose": None}

        def decider(state, body, op):
            # The wrapped op exposes the same surface plus DB augmentation.
            result = op.query_component_db(
                "BJT_NPN:thermal_runaway",
                component_type="BJT_NPN",
                failure_mode="thermal_runaway",
            )
            if result.get("success") and isinstance(result.get("db"), dict):
                observed["saw_db"] = True
                best = result["db"].get("best")
                if best:
                    observed["best_repurpose"] = best.get("repurpose_option")
            return None

        with tempfile.TemporaryDirectory() as d:
            _fixture_dir(d)
            adapter = ComponentDBAdapter(matrices_dir=d)
            Session(
                scenario_name="thermal_drift_localized",
                ai_decide=decider,
                output_dir=os.path.join(d, "session"),
                seed=0,
                max_ticks=5,
                db_adapter=adapter,
            ).run()

        self.assertTrue(observed["saw_db"])
        # Best option for (BJT_NPN, thermal_runaway) in the fixture
        # is "Temperature Sensor" (High effectiveness).
        self.assertEqual(observed["best_repurpose"], "Temperature Sensor")

    def test_session_without_db_adapter_unchanged(self):
        from scenario_engine.runner import Session
        observed = {"db_key_present": False}

        def decider(state, body, op):
            r = op.query_component_db("k")
            observed["db_key_present"] = "db" in r
            return None

        with tempfile.TemporaryDirectory() as d:
            Session(
                scenario_name="thermal_drift_localized",
                ai_decide=decider,
                output_dir=os.path.join(d, "session"),
                seed=0,
                max_ticks=5,
                # db_adapter omitted
            ).run()

        # No wrapping → no 'db' key in the response.
        self.assertFalse(observed["db_key_present"])


if __name__ == "__main__":
    unittest.main()
