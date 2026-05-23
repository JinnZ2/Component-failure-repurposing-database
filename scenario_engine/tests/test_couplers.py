"""Tests for the scenario_engine.couplers subpackage."""

import unittest

from scenario_engine.couplers import CATALOG, Coupler, build
from scenario_engine.scenarios import CrossSubstrateCoupling


class CouplerDataclassTests(unittest.TestCase):
    def test_apply_multiplies_by_ratio(self):
        c = Coupler(
            name="test",
            kind="transformer",
            ratio=2.5,
            port_in="thermal",
            port_out="mechanical",
        )
        self.assertEqual(c.apply(4.0), 10.0)
        self.assertEqual(c.apply(0.0), 0.0)
        self.assertEqual(c.apply(-1.0), -2.5)

    def test_frozen(self):
        c = Coupler(
            name="t", kind="transformer", ratio=1.0,
            port_in="a", port_out="b",
        )
        with self.assertRaises(Exception):
            c.ratio = 2.0  # frozen dataclass


class CatalogTests(unittest.TestCase):
    def test_known_entries(self):
        self.assertIn("thermal_expansion_to_strain", CATALOG)
        self.assertIn("pcb_strain_to_cap_esr", CATALOG)
        self.assertIn("cap_esr_to_rail_noise", CATALOG)

    def test_build_thermal_expansion(self):
        c = build(
            "thermal_expansion_to_strain",
            geometry={"expansion_per_C_mm": 0.012},
        )
        self.assertEqual(c.kind, "transformer")
        self.assertEqual(c.port_in, "thermal")
        self.assertEqual(c.port_out, "mechanical")
        self.assertEqual(c.ratio, 0.012)
        # ΔT of 50K → 0.6 mm strain
        self.assertAlmostEqual(c.apply(50.0), 0.6, places=6)

    def test_build_strain_to_esr(self):
        c = build(
            "pcb_strain_to_cap_esr",
            geometry={"esr_per_mm_strain": 0.4},
        )
        self.assertEqual(c.kind, "gyrator")
        self.assertEqual(c.ratio, 0.4)

    def test_build_esr_to_noise(self):
        c = build(
            "cap_esr_to_rail_noise",
            geometry={"noise_v_per_ohm_esr": 0.8},
        )
        self.assertEqual(c.kind, "transformer")
        self.assertEqual(c.ratio, 0.8)

    def test_unknown_coupler_raises(self):
        with self.assertRaises(KeyError):
            build("not_a_coupler", geometry={})

    def test_provenance_records_catalog_lookup(self):
        c = build(
            "thermal_expansion_to_strain",
            geometry={"expansion_per_C_mm": 0.012},
        )
        self.assertIn("CATALOG", c.provenance)
        self.assertIn("thermal_expansion_to_strain", c.provenance)


class UpstreamCatalogBackfillTests(unittest.TestCase):
    """Entries adopted verbatim from Geometric-to-Binary fabrication/."""

    def test_horn_acoustic(self):
        c = build("horn_acoustic", geometry={"area_in": 4.0, "area_out": 1.0})
        self.assertEqual(c.kind, "transformer")
        self.assertEqual(c.port_in, "acoustic")
        self.assertEqual(c.port_out, "acoustic")
        self.assertEqual(c.ratio, 4.0)

    def test_piezo_disc(self):
        c = build(
            "piezo_disc",
            geometry={"d33": 400e-12, "area": 1e-4, "thickness": 1e-3},
        )
        self.assertEqual(c.kind, "gyrator")
        self.assertEqual(c.port_in, "electrical")
        self.assertEqual(c.port_out, "mechanical")
        self.assertAlmostEqual(c.ratio, 400e-12 * 1e-4 / 1e-3, places=18)

    def test_syringe_pump(self):
        c = build("syringe_pump", geometry={"piston_area": 0.01})
        self.assertEqual(c.kind, "transformer")
        self.assertEqual(c.port_in, "mechanical")
        self.assertEqual(c.port_out, "fluidic")
        self.assertEqual(c.ratio, 0.01)

    def test_diaphragm_speaker(self):
        c = build("diaphragm_speaker", geometry={"BL": 5.0})
        self.assertEqual(c.kind, "gyrator")
        self.assertEqual(c.port_in, "electrical")
        self.assertEqual(c.port_out, "acoustic")
        self.assertEqual(c.ratio, 5.0)


class CouplerSerializationTests(unittest.TestCase):
    def test_to_dict_contains_provenance(self):
        c = build(
            "thermal_expansion_to_strain",
            geometry={"expansion_per_C_mm": 0.012},
        )
        d = c.to_dict()
        self.assertEqual(d["name"], "thermal_expansion_to_strain")
        self.assertEqual(d["kind"], "transformer")
        self.assertEqual(d["ratio"], 0.012)
        self.assertIn("CATALOG", d["provenance"])
        self.assertEqual(d["geometry"], {"expansion_per_C_mm": 0.012})


class ScenarioStateCouplersFieldTests(unittest.TestCase):
    def test_cross_substrate_step_populates_couplers(self):
        s = CrossSubstrateCoupling()
        state = s.step()
        self.assertIn("thermal_to_strain", state.couplers)
        self.assertIn("strain_to_esr", state.couplers)
        self.assertIn("esr_to_noise", state.couplers)
        # Each entry carries the expected provenance shape.
        thermal = state.couplers["thermal_to_strain"]
        self.assertEqual(thermal["kind"], "transformer")
        self.assertEqual(thermal["ratio"], 0.012)
        self.assertEqual(thermal["port_in"], "thermal")
        self.assertEqual(thermal["port_out"], "mechanical")

    def test_to_dict_round_trip_includes_couplers(self):
        s = CrossSubstrateCoupling()
        state = s.step()
        d = state.to_dict()
        self.assertIn("couplers", d)
        self.assertEqual(set(d["couplers"].keys()),
                         {"thermal_to_strain", "strain_to_esr", "esr_to_noise"})


class CrossSubstrateRefactorBehaviorTests(unittest.TestCase):
    """The coupler refactor must preserve scenario outputs exactly."""

    def test_known_tick_values_match_pre_refactor(self):
        """Hand-computed values from the original linear-math implementation."""
        s = CrossSubstrateCoupling(seed=0, max_ticks=200)
        # Step through ticks 0..49 to land after the drift starts (tick 10).
        for _ in range(50):
            state = s.step()

        # At tick 49 (50 steps; last yielded state.tick == 49):
        # ticks_drifting = 49 - 10 = 39
        # Q1_T = 65 + 0.8 * 39 = 96.2
        Q1_T_expected = 65.0 + 0.8 * 39
        # PCB strain = (Q1_T - 25) * 0.012
        strain_expected = (Q1_T_expected - 25.0) * 0.012
        # C1 ESR = 0.05 + 0.4 * strain
        esr_expected = 0.05 + 0.4 * strain_expected
        # Rail noise = 0.002 + 0.8 * esr
        noise_expected = 0.002 + 0.8 * esr_expected

        self.assertAlmostEqual(
            state.actual_outcome["Q1_temp_c"], round(Q1_T_expected, 2), places=2
        )
        self.assertAlmostEqual(
            state.actual_outcome["PCB_strain_mm"], round(strain_expected, 4), places=4
        )
        self.assertAlmostEqual(
            state.actual_outcome["C1_esr_ohm"], round(esr_expected, 4), places=4
        )
        self.assertAlmostEqual(
            state.actual_outcome["rail_noise_v"], round(noise_expected, 5), places=5
        )

    def test_coupler_objects_are_inspectable(self):
        """A scenario user (or audit tool) can read the active couplers."""
        s = CrossSubstrateCoupling()
        self.assertEqual(s.coupler_thermal_to_strain.ratio, 0.012)
        self.assertEqual(s.coupler_strain_to_esr.ratio, 0.4)
        self.assertEqual(s.coupler_esr_to_noise.ratio, 0.8)
        self.assertEqual(s.coupler_thermal_to_strain.kind, "transformer")
        self.assertEqual(s.coupler_strain_to_esr.kind, "gyrator")


if __name__ == "__main__":
    unittest.main()
