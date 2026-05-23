"""Tests for the scenario_engine.physics module (pipe_modes, eigenmodes)."""

import math
import unittest
from dataclasses import dataclass

from scenario_engine.physics import (
    C_AIR,
    J_PRIME_ZEROS,
    box_modes,
    cylinder_modes,
    ka_check,
    pipe_modes,
    predict_eigenmodes,
    predict_eigenmodes_full,
)


class PipeModeTests(unittest.TestCase):
    def test_open_open_first_mode(self):
        # f_1 = c / (2L); for L=1m, c=343 → 171.5 Hz
        modes = pipe_modes(1.0, "open_open", n_max=1)
        self.assertEqual(len(modes), 1)
        self.assertAlmostEqual(modes[0]["f"], 343.0 / 2.0, places=3)
        self.assertEqual(modes[0]["axial_n"], 1)
        self.assertEqual(modes[0]["end"], "open_open")

    def test_open_closed_lower_first_mode(self):
        # f_1 = c/(4L) for open_closed → half of open_open
        modes_oc = pipe_modes(1.0, "open_closed", n_max=1)
        modes_oo = pipe_modes(1.0, "open_open", n_max=1)
        self.assertAlmostEqual(modes_oc[0]["f"], modes_oo[0]["f"] / 2, places=3)

    def test_unknown_end_condition_raises(self):
        with self.assertRaises(ValueError):
            pipe_modes(1.0, "bogus", n_max=1)

    def test_n_max_returns_requested_count(self):
        self.assertEqual(len(pipe_modes(1.0, "open_open", n_max=4)), 4)


class BoxModeTests(unittest.TestCase):
    def test_cube_first_mode(self):
        # Cubic box 1×1×1 m → first mode at f = c/(2L) = 171.5 Hz
        modes = box_modes(1.0, 1.0, 1.0, n_max=1)
        self.assertGreater(len(modes), 0)
        # Lowest mode is (1,0,0) family with f = c/2
        self.assertAlmostEqual(modes[0]["f"], 343.0 / 2.0, places=3)
        # Modes are sorted ascending
        freqs = [m["f"] for m in modes]
        self.assertEqual(freqs, sorted(freqs))

    def test_excludes_000_mode(self):
        # (0,0,0) is excluded by construction
        for m in box_modes(1.0, 1.0, 1.0, n_max=2):
            self.assertNotEqual(m["indices"], (0, 0, 0))

    def test_mode_index_consecutive(self):
        modes = box_modes(1.0, 2.0, 3.0, n_max=2)
        for i, m in enumerate(modes):
            self.assertEqual(m["mode_index"], i)


class CylinderModeTests(unittest.TestCase):
    def test_axial_modes_present(self):
        modes = cylinder_modes(0.05, 1.0, n_axial=2, m_radial=1)
        # First axial mode: f = c/(2L) = 171.5 Hz
        axial_modes = [m for m in modes if m["radial"] == (0, 0)]
        self.assertGreater(len(axial_modes), 0)
        self.assertAlmostEqual(axial_modes[0]["f"], 343.0 / 2.0, places=3)


class KaCheckTests(unittest.TestCase):
    def test_returns_dimensionless_number(self):
        geom = {"characteristic_dim_m": 0.04, "lumped_f_lowest_Hz": 170.0}
        ka = ka_check(geom)
        # k = 2π·f/c; ka = k·a
        expected = 2 * math.pi * 170.0 / 343.0 * 0.04
        self.assertAlmostEqual(ka, expected, places=6)


# Synthetic IR-like object for eigenmodes tests (the real IR module
# lives upstream; this is the minimal duck type predict_eigenmodes
# needs).

@dataclass
class _Element:
    kind: str
    parameter: float


@dataclass
class _IR:
    elements: list


class EigenmodesTests(unittest.TestCase):
    def test_single_lc_pair_gives_one_mode(self):
        ir = _IR(elements=[
            _Element("store_effort", 1e-6),   # 1 µF
            _Element("store_flow", 1e-3),     # 1 mH
        ])
        modes = predict_eigenmodes(ir)
        self.assertEqual(len(modes), 1)
        # f = 1 / (2π·√(LC))
        expected = 1.0 / (2 * math.pi * math.sqrt(1e-3 * 1e-6))
        self.assertAlmostEqual(modes[0]["f"], expected, places=2)
        self.assertEqual(modes[0]["kind"], "lumped")

    def test_empty_ir_returns_empty(self):
        self.assertEqual(predict_eigenmodes(_IR(elements=[])), [])

    def test_predict_full_no_hints_falls_back_to_lumped(self):
        ir = _IR(elements=[
            _Element("store_effort", 1e-6),
            _Element("store_flow", 1e-3),
        ])
        out = predict_eigenmodes_full(ir, geometry_hints=None)
        self.assertEqual(len(out), 1)

    def test_predict_full_distributed_box(self):
        # ka > 0.3 trigger: characteristic_dim_m = 0.5 at f_lowest = 200 Hz
        # ka = 2π·200/343 · 0.5 ≈ 1.83 (well above 0.3)
        out = predict_eigenmodes_full(
            ir=None,
            geometry_hints={
                "distributed": "box",
                "Lx": 1.0, "Ly": 1.0, "Lz": 1.0,
                "n_max": 1,
                "characteristic_dim_m": 0.5,
                "lumped_f_lowest_Hz": 200.0,
            },
        )
        self.assertGreater(len(out), 0)
        # Lowest box mode should be at c/2 ≈ 171.5 Hz
        self.assertAlmostEqual(out[0]["f"], 343.0 / 2.0, places=3)


class BesselTablesTests(unittest.TestCase):
    def test_j_prime_zeros_have_three_orders(self):
        for m in range(4):
            self.assertIn(m, J_PRIME_ZEROS)
            self.assertEqual(len(J_PRIME_ZEROS[m]), 3)

    def test_c_air_default(self):
        self.assertEqual(C_AIR, 343.0)


if __name__ == "__main__":
    unittest.main()
