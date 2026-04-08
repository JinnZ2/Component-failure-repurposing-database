#!/usr/bin/env python3
"""
Quantum Chemistry with Geometric States
=========================================
Maps molecular electron density to octahedral tokens so that molecular
symmetry, bonding, and reaction events appear as geometric dependencies
(cube cancellations / tensor cancellations) detectable by the existing
GEIS pipeline.

Pipeline:
  1. Load molecule geometry (.xyz format or inline coordinates)
  2. Compute electron density on a 3D grid (superposition of atomic
     densities with Slater-type exponential decay)
  3. At each grid point, compute the density gradient direction
     -> octahedral vertex (3-bit state, 0-7)
  4. Magnitude -> operator (| high, / low)
  5. Orbital character -> symbol (O=s, I=p, X=d, delta=f/mixed)
  6. Feed token stream into 3D cube -> detect symmetry via cube hash
  7. Tensor accumulation -> detect bonding dependencies

Molecules included for demo:
  - H2 (diatomic, D_inf_h symmetry)
  - H2O (bent, C2v symmetry)
  - CH4 (tetrahedral, Td symmetry)
  - NH3 (pyramidal, C3v symmetry)

Requires: numpy

Connects to:
  - geometric_sensing_sim.py: OctahedralState, GeometricEncoder, StateTensor
  - geometric_transport_sieve.py: SOMS polyhedron (electron flow model)
  - geometric_failure_diagnosis.py: DatabaseInterface pattern

Future:
  - Interface with PySCF/Psi4 for real density matrices
  - Reaction monitoring: move atoms, watch cube hash change
  - Electron flow transport on rhombic triacontahedron graph
"""

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# -- Import GEIS classes from sibling module ----------------------------
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from geometric_sensing_sim import (  # noqa: E402
    GeometricEncoder,
    OctahedralState,
    StateTensor,
    find_tensor_dependencies,
    tensor_norm,
    token_to_tensor,
)


# ======================================================================
# Atomic data
# ======================================================================

# Effective nuclear charges (Slater's rules, simplified)
ATOMIC_Z = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6,
    "N": 7, "O": 8, "F": 9, "Ne": 10, "Na": 11, "S": 16,
    "Cl": 17, "Fe": 26,
}

# Slater exponents (STO-3G-like, approximate zeta for 1s orbitals)
SLATER_ZETA = {
    "H": 1.24, "He": 1.69, "Li": 0.65, "Be": 0.98, "B": 1.30,
    "C": 1.63, "N": 1.95, "O": 2.28, "F": 2.60, "Ne": 2.93,
    "Na": 0.84, "S": 1.83, "Cl": 2.04, "Fe": 1.70,
}

# Dominant orbital character by element (simplified)
ORBITAL_CHAR = {
    "H": "s", "He": "s", "Li": "s", "Be": "s", "B": "p",
    "C": "p", "N": "p", "O": "p", "F": "p", "Ne": "p",
    "Na": "s", "S": "p", "Cl": "p", "Fe": "d",
}


# ======================================================================
# Molecule representation
# ======================================================================

@dataclass
class Atom:
    symbol: str
    position: np.ndarray  # (3,) in angstroms

    @property
    def Z(self) -> int:
        return ATOMIC_Z.get(self.symbol, 1)

    @property
    def zeta(self) -> float:
        return SLATER_ZETA.get(self.symbol, 1.0)

    @property
    def orbital(self) -> str:
        return ORBITAL_CHAR.get(self.symbol, "s")


@dataclass
class Molecule:
    name: str
    atoms: List[Atom]
    symmetry: str = ""  # e.g. "C2v", "Td"

    @classmethod
    def from_xyz(cls, text: str, name: str = "molecule",
                 symmetry: str = "") -> "Molecule":
        """Parse XYZ format: first line = atom count, second = comment,
        then symbol x y z per line."""
        lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
        n_atoms = int(lines[0])
        atoms = []
        for line in lines[2:2 + n_atoms]:
            parts = line.split()
            sym = parts[0]
            pos = np.array([float(parts[1]), float(parts[2]),
                            float(parts[3])])
            atoms.append(Atom(symbol=sym, position=pos))
        return cls(name=name, atoms=atoms, symmetry=symmetry)

    def center_of_mass(self) -> np.ndarray:
        total_z = sum(a.Z for a in self.atoms)
        return sum(a.Z * a.position for a in self.atoms) / total_z


# -- Built-in molecules ------------------------------------------------

def water() -> Molecule:
    """H2O — C2v symmetry, bond angle ~104.5 deg."""
    return Molecule("H2O", [
        Atom("O", np.array([0.0, 0.0, 0.0])),
        Atom("H", np.array([0.757, 0.587, 0.0])),
        Atom("H", np.array([-0.757, 0.587, 0.0])),
    ], symmetry="C2v")


def hydrogen() -> Molecule:
    """H2 — D_inf_h symmetry, bond length ~0.74 A."""
    return Molecule("H2", [
        Atom("H", np.array([0.0, 0.0, -0.37])),
        Atom("H", np.array([0.0, 0.0, 0.37])),
    ], symmetry="D_inf_h")


def methane() -> Molecule:
    """CH4 — Td symmetry."""
    d = 1.09 / math.sqrt(3)
    return Molecule("CH4", [
        Atom("C", np.array([0.0, 0.0, 0.0])),
        Atom("H", np.array([d, d, d])),
        Atom("H", np.array([d, -d, -d])),
        Atom("H", np.array([-d, d, -d])),
        Atom("H", np.array([-d, -d, d])),
    ], symmetry="Td")


def ammonia() -> Molecule:
    """NH3 — C3v symmetry."""
    return Molecule("NH3", [
        Atom("N", np.array([0.0, 0.0, 0.0])),
        Atom("H", np.array([0.0, 0.94, -0.38])),
        Atom("H", np.array([0.81, -0.47, -0.38])),
        Atom("H", np.array([-0.81, -0.47, -0.38])),
    ], symmetry="C3v")


# ======================================================================
# Electron density computation
# ======================================================================

def atomic_density(r: np.ndarray, atom: Atom) -> float:
    """
    Slater-type orbital density at point r from a single atom.
    rho(r) = Z * exp(-2 * zeta * |r - R|)
    """
    d = np.linalg.norm(r - atom.position)
    return atom.Z * math.exp(-2.0 * atom.zeta * d)


def density_gradient(r: np.ndarray, mol: Molecule,
                     eps: float = 0.05) -> np.ndarray:
    """
    Numerical gradient of total electron density at point r.
    Central differences with step eps.
    """
    grad = np.zeros(3)
    for axis in range(3):
        r_plus = r.copy()
        r_minus = r.copy()
        r_plus[axis] += eps
        r_minus[axis] -= eps
        rho_plus = sum(atomic_density(r_plus, a) for a in mol.atoms)
        rho_minus = sum(atomic_density(r_minus, a) for a in mol.atoms)
        grad[axis] = (rho_plus - rho_minus) / (2.0 * eps)
    return grad


# ======================================================================
# Grid point -> geometric token
# ======================================================================

ORBITAL_SYMBOL = {"s": "O", "p": "I", "d": "X", "f": "\u0394"}


def grid_point_to_token(r: np.ndarray, mol: Molecule,
                        density_threshold: float = 0.5) -> str:
    """
    Map a single grid point to a geometric token.

    - Vertex (3 bits): direction of density gradient -> closest
      octahedral vertex
    - Operator: | if total density > threshold, / if low
    - Symbol: dominant orbital character of nearest atom
    """
    # Total density
    rho = sum(atomic_density(r, a) for a in mol.atoms)

    # Gradient direction -> octahedral vertex
    grad = density_gradient(r, mol)
    grad_norm = np.linalg.norm(grad)
    if grad_norm < 1e-10:
        # At a critical point (nucleus or saddle) — use direction to
        # nearest atom instead
        dists = [(np.linalg.norm(r - a.position), a) for a in mol.atoms]
        nearest_atom = min(dists, key=lambda x: x[0])[1]
        direction = nearest_atom.position - r
        if np.linalg.norm(direction) < 1e-10:
            direction = np.array([0.0, 0.0, 1.0])
    else:
        direction = grad

    state = OctahedralState.closest(direction)
    vertex = state.to_binary()

    # Operator from density magnitude
    operator = "|" if rho > density_threshold else "/"

    # Symbol from nearest atom's orbital character
    dists = [(np.linalg.norm(r - a.position), a) for a in mol.atoms]
    nearest = min(dists, key=lambda x: x[0])[1]
    symbol = ORBITAL_SYMBOL.get(nearest.orbital, "O")

    return f"{vertex}{operator}{symbol}"


# ======================================================================
# Molecule -> token grid -> cube
# ======================================================================

def molecule_to_token_grid(mol: Molecule, grid_size: int = 4,
                           padding: float = 1.5
                           ) -> Tuple[List[str], np.ndarray]:
    """
    Compute geometric tokens on a 3D grid around the molecule.

    Returns:
      tokens: flat list of tokens (grid_size^3 length)
      density_grid: 3D array of total electron density values
    """
    # Grid bounds from atomic positions
    positions = np.array([a.position for a in mol.atoms])
    lo = positions.min(axis=0) - padding
    hi = positions.max(axis=0) + padding

    xs = np.linspace(lo[0], hi[0], grid_size)
    ys = np.linspace(lo[1], hi[1], grid_size)
    zs = np.linspace(lo[2], hi[2], grid_size)

    # Adaptive density threshold: median of sampled densities
    sample_rhos = []
    for xi in xs:
        for yj in ys:
            for zk in zs:
                r = np.array([xi, yj, zk])
                sample_rhos.append(
                    sum(atomic_density(r, a) for a in mol.atoms))
    threshold = float(np.median(sample_rhos))

    tokens: List[str] = []
    density_grid = np.zeros((grid_size, grid_size, grid_size))

    for i, xi in enumerate(xs):
        for j, yj in enumerate(ys):
            for k, zk in enumerate(zs):
                r = np.array([xi, yj, zk])
                rho = sum(atomic_density(r, a) for a in mol.atoms)
                density_grid[i, j, k] = rho
                token = grid_point_to_token(r, mol, threshold)
                tokens.append(token)

    return tokens, density_grid


def tokens_to_cube(tokens: List[str], side: int) -> np.ndarray:
    """Pack token vertex bits into a 3D cube."""
    cube = np.zeros((side, side, side), dtype=np.uint8)
    idx = 0
    for i in range(side):
        for j in range(side):
            for k in range(side):
                if idx < len(tokens):
                    cube[i, j, k] = int(tokens[idx][:3], 2)
                idx += 1
    return cube


# ======================================================================
# Symmetry detection via cube rotation
# ======================================================================

def _rotate_cube_180_y(cube: np.ndarray) -> np.ndarray:
    """180 deg rotation around Y axis = rot90 twice in (0,2) plane."""
    return np.rot90(cube, k=2, axes=(0, 2))


def _rotate_cube_180_z(cube: np.ndarray) -> np.ndarray:
    """180 deg rotation around Z axis = rot90 twice in (0,1) plane."""
    return np.rot90(cube, k=2, axes=(0, 1))


def _rotate_cube_120_diag(cube: np.ndarray) -> np.ndarray:
    """Approximate 120 deg rotation: cyclic permute axes (x->y->z->x)."""
    return np.transpose(cube, (2, 0, 1))


def _invert_cube(cube: np.ndarray) -> np.ndarray:
    """Inversion through centre: flip all axes."""
    return cube[::-1, ::-1, ::-1]


def cube_hash(cube: np.ndarray) -> bytes:
    return cube.tobytes()


def detect_symmetry(cube: np.ndarray) -> List[str]:
    """
    Test a set of rotation/inversion operations and report which
    leave the cube invariant (symmetry operations detected).
    """
    ops = {
        "C2(y)":  _rotate_cube_180_y,
        "C2(z)":  _rotate_cube_180_z,
        "C3(diag)": _rotate_cube_120_diag,
        "i (inversion)": _invert_cube,
        "E (identity)": lambda c: c,
    }
    original_hash = cube_hash(cube)
    detected = []
    for name, op in ops.items():
        transformed = op(cube.copy())
        if cube_hash(transformed) == original_hash:
            detected.append(name)
    return detected


# ======================================================================
# Bond analysis via tensor dependencies
# ======================================================================

def analyze_bonds(mol: Molecule, tokens: List[str],
                  grid_size: int = 4) -> List[Dict]:
    """
    Find tensor dependencies in the token grid.
    Dependencies between tokens near different atoms suggest bonding
    interactions (shared electron density).
    """
    positions = np.array([a.position for a in mol.atoms])
    lo = positions.min(axis=0) - 1.5
    hi = positions.max(axis=0) + 1.5

    xs = np.linspace(lo[0], hi[0], grid_size)
    ys = np.linspace(lo[1], hi[1], grid_size)
    zs = np.linspace(lo[2], hi[2], grid_size)

    # Map each token index to its nearest atom
    grid_points = []
    for xi in xs:
        for yj in ys:
            for zk in zs:
                grid_points.append(np.array([xi, yj, zk]))

    token_atoms = []
    for r in grid_points:
        dists = [(np.linalg.norm(r - a.position), a.symbol)
                 for a in mol.atoms]
        token_atoms.append(min(dists, key=lambda x: x[0])[1])

    # Find tensor dependencies
    deps = find_tensor_dependencies(tokens, max_len=3)

    bonds = []
    for dep in deps:
        atoms_involved = set(token_atoms[i] for i in dep
                             if i < len(token_atoms))
        if len(atoms_involved) >= 2:
            toks = [tokens[i] for i in dep]
            T_sum = sum(token_to_tensor(t) for t in toks)
            bonds.append({
                "indices": dep,
                "tokens": toks,
                "atoms": atoms_involved,
                "tensor_norm": tensor_norm(T_sum),
                "type": "bonding" if len(atoms_involved) == 2
                        else "multi-center",
            })

    return bonds


# ======================================================================
# Reaction simulation: bond stretching
# ======================================================================

def stretch_bond(mol: Molecule, atom_idx_a: int, atom_idx_b: int,
                 distances: List[float], grid_size: int = 4
                 ) -> List[Tuple[float, List[str], np.ndarray]]:
    """
    Stretch a bond between two atoms and return the token grid at
    each distance.  Useful for watching cube hash change during a
    reaction (bond breaking).
    """
    a = mol.atoms[atom_idx_a]
    b = mol.atoms[atom_idx_b]
    direction = b.position - a.position
    direction = direction / np.linalg.norm(direction)

    results = []
    for d in distances:
        # Create stretched molecule
        stretched_atoms = []
        for i, atom in enumerate(mol.atoms):
            if i == atom_idx_b:
                new_pos = a.position + direction * d
                stretched_atoms.append(Atom(atom.symbol, new_pos))
            else:
                stretched_atoms.append(Atom(atom.symbol,
                                            atom.position.copy()))
        stretched = Molecule(f"{mol.name}_d={d:.2f}", stretched_atoms)
        tokens, density = molecule_to_token_grid(stretched, grid_size)
        results.append((d, tokens, density))

    return results


# ======================================================================
# Demo
# ======================================================================

def demo():
    print("=" * 70)
    print("QUANTUM CHEMISTRY WITH GEOMETRIC STATES")
    print("Electron density -> octahedral tokens -> symmetry detection")
    print("=" * 70)

    encoder = GeometricEncoder()
    grid_size = 4
    molecules = [hydrogen(), water(), methane(), ammonia()]

    for mol in molecules:
        print(f"\n{'─' * 70}")
        print(f"  {mol.name}  ({mol.symmetry})")
        print(f"  Atoms: {[(a.symbol, tuple(np.round(a.position, 3))) for a in mol.atoms]}")
        print(f"{'─' * 70}")

        # Compute token grid
        tokens, density = molecule_to_token_grid(mol, grid_size)
        cube = tokens_to_cube(tokens, grid_size)

        # Token summary
        unique_tokens = set(tokens)
        print(f"\n  Grid: {grid_size}x{grid_size}x{grid_size} = "
              f"{len(tokens)} tokens  ({len(unique_tokens)} unique)")
        print(f"  Density range: {density.min():.4f} - {density.max():.4f}")

        # Show sample tokens
        print(f"\n  Sample tokens (corners of grid):")
        corners = [0, grid_size - 1, grid_size ** 2 - 1,
                   grid_size ** 3 - 1]
        for idx in corners:
            if idx < len(tokens):
                t = tokens[idx]
                binary = encoder.encode_to_binary(t)
                state = OctahedralState.from_token(t)
                T = StateTensor(state)
                print(f"    [{idx:>3}] {t}  binary={binary}  "
                      f"tensor trace={T.trace():.4f}")

        # Symmetry detection
        detected = detect_symmetry(cube)
        print(f"\n  Symmetry operations detected: {detected}")
        if "E (identity)" in detected and len(detected) > 1:
            non_trivial = [s for s in detected if s != "E (identity)"]
            print(f"  Non-trivial symmetries: {non_trivial}")
            print(f"  -> Consistent with {mol.symmetry} point group")

        # Tensor dependencies (bonding)
        bonds = analyze_bonds(mol, tokens, grid_size)
        if bonds:
            print(f"\n  Tensor dependencies (bonding interactions): "
                  f"{len(bonds)}")
            for b in bonds[:5]:
                print(f"    {b['atoms']} ({b['type']}) "
                      f"norm={b['tensor_norm']:.2e}  "
                      f"tokens={b['tokens']}")
        else:
            print(f"\n  No tensor cancellations (all grid points "
                  f"geometrically distinct)")

    # -- Bond stretching demo: H2 dissociation -------------------------
    print(f"\n{'=' * 70}")
    print("  H2 BOND STRETCHING (dissociation curve)")
    print(f"{'=' * 70}")

    mol = hydrogen()
    distances = [0.5, 0.74, 1.0, 1.5, 2.0, 3.0, 5.0]
    results = stretch_bond(mol, 0, 1, distances, grid_size)

    print(f"\n  {'Dist':>6}  {'Unique tokens':>14}  "
          f"{'Max density':>12}  {'Symmetries'}")
    print(f"  {'-' * 6}  {'-' * 14}  {'-' * 12}  {'-' * 30}")

    for d, tokens, density in results:
        cube = tokens_to_cube(tokens, grid_size)
        syms = detect_symmetry(cube)
        non_trivial = [s for s in syms if s != "E (identity)"]
        print(f"  {d:>6.2f}  {len(set(tokens)):>14}  "
              f"{density.max():>12.4f}  {non_trivial}")

    print(f"\n  As bond stretches:")
    print(f"    - Density maximum decreases (atoms separate)")
    print(f"    - Token diversity changes (symmetry breaking/recovery)")
    print(f"    - Cube hash changes track the reaction coordinate")

    # -- Repurposing connection ----------------------------------------
    print(f"\n{'=' * 70}")
    print("  CONNECTION TO COMPONENT REPURPOSING")
    print(f"{'=' * 70}")
    print("""
  The same geometric pipeline used for electron density analysis
  applies to component failure monitoring:

    Quantum chemistry          Component repurposing
    ──────────────────         ─────────────────────
    Atom positions       <->   Sensor readings
    Electron density     <->   Component health score
    Density gradient     <->   Drift direction
    Octahedral token     <->   Failure mode token
    Cube dependency      <->   Repeated failure pattern
    Bond breaking        <->   Component degradation
    Symmetry detection   <->   Periodic failure cycles

  A future AI system could use identical OctahedralState / StateTensor
  classes to analyse both molecular reactions and hardware failures,
  detecting patterns that bridge chemistry and engineering.
""")


if __name__ == "__main__":
    demo()
