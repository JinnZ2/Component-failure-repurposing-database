#!/usr/bin/env python3
"""
Molecule to Geometric Tokens: Symmetry Detection via Fourier Cube Hash
=====================================================================
Maps electron density of small molecules to a 3D grid of octahedral tokens,
then detects rotational symmetry using rotation‑invariant cube hashing.
"""

import math
import numpy as np
from itertools import product

# ----------------------------------------------------------------------
# 1. Octahedral state helpers (from earlier)
# ----------------------------------------------------------------------
def vector_to_octahedral_vertex(v):
    """
    Find the closest octahedral vertex direction (0-7) for a given 3D vector.
    Octahedral vertices are (±1,±1,±1) / √3.
    """
    # Normalize
    v = v / np.linalg.norm(v)
    # Octahedral vertices
    vertices = []
    for ix in (-1,1):
        for iy in (-1,1):
            for iz in (-1,1):
                vertices.append(np.array([ix,iy,iz]) / math.sqrt(3))
    # Compute dot products
    dots = [np.dot(v, vert) for vert in vertices]
    return int(np.argmax(dots))

def density_to_token(rho, grad):
    """
    Convert electron density and gradient to an octahedral token.
    - Vertex: direction of gradient (or of density maximum)
    - Operator: '|' if density > threshold, else '/'
    - Symbol: 'O' (simplified – could encode spin/orbital)
    """
    # Vertex from gradient direction (if gradient is zero, use (0,0,1))
    if np.linalg.norm(grad) < 1e-6:
        grad = np.array([0,0,1])
    vertex = vector_to_octahedral_vertex(grad)
    vertex_bits = f"{vertex:03b}"
    # Operator based on density magnitude
    threshold = 0.05   # tune
    operator = '|' if rho > threshold else '/'
    # Symbol (placeholder – could be derived from spin density)
    symbol = 'O'
    return f"{vertex_bits}{operator}{symbol}"

# ----------------------------------------------------------------------
# 2. Simple electron density model (superposition of atomic densities)
# ----------------------------------------------------------------------
def atomic_density(r, R, Z=1, decay=2.0):
    """Exponential decay model: ρ(r) = Z * exp(-decay * |r-R|)."""
    d = np.linalg.norm(r - R)
    return Z * math.exp(-decay * d)

def molecule_density(coords, charges, grid_points):
    """
    Compute total electron density at a list of grid points.
    coords: list of (x,y,z) for each atom
    charges: nuclear charges (Z)
    grid_points: array of shape (N,3)
    Returns array of densities.
    """
    densities = np.zeros(len(grid_points))
    for i, pt in enumerate(grid_points):
        total = 0.0
        for R, Z in zip(coords, charges):
            total += atomic_density(pt, np.array(R), Z, decay=1.5)
        densities[i] = total
    return densities

def density_gradient(r, coords, charges, eps=1e-5):
    """Numerical gradient of density at point r."""
    grad = np.zeros(3)
    for dim in range(3):
        r_plus = r.copy()
        r_minus = r.copy()
        r_plus[dim] += eps
        r_minus[dim] -= eps
        rho_plus = molecule_density(coords, charges, [r_plus])[0]
        rho_minus = molecule_density(coords, charges, [r_minus])[0]
        grad[dim] = (rho_plus - rho_minus) / (2*eps)
    return grad

# ----------------------------------------------------------------------
# 3. Build 3D cube of tokens for a molecule
# ----------------------------------------------------------------------
def molecule_to_token_cube(coords, charges, side=8, bounds=None):
    """
    Map molecule to a 3D cube (side x side x side) of octahedral tokens.
    Returns a numpy array of shape (side,side,side) with integer state values (0-7).
    Also returns the cube of full tokens (strings) if needed.
    """
    if bounds is None:
        # Determine bounding box from coordinates
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        zs = [c[2] for c in coords]
        min_x, max_x = min(xs)-1.0, max(xs)+1.0
        min_y, max_y = min(ys)-1.0, max(ys)+1.0
        min_z, max_z = min(zs)-1.0, max(zs)+1.0
    else:
        min_x, max_x, min_y, max_y, min_z, max_z = bounds

    # Create grid points
    x_vals = np.linspace(min_x, max_x, side)
    y_vals = np.linspace(min_y, max_y, side)
    z_vals = np.linspace(min_z, max_z, side)
    grid = np.array(list(product(x_vals, y_vals, z_vals)))

    # Compute densities at all points
    densities = molecule_density(coords, charges, grid)
    # Reshape to cube
    density_cube = densities.reshape(side, side, side)

    # Compute gradients for each point (could be slow; for demo we do simple)
    grad_cube = np.zeros((side, side, side, 3))
    for i, pt in enumerate(grid):
        grad = density_gradient(pt, coords, charges)
        grad_cube.reshape(-1,3)[i] = grad

    # Convert each grid point to token vertex (0-7) and store as integer
    state_cube = np.zeros((side, side, side), dtype=np.uint8)
    token_cube = np.empty((side, side, side), dtype=object)
    for i in range(side):
        for j in range(side):
            for k in range(side):
                idx = i*side*side + j*side + k
                rho = density_cube[i,j,k]
                grad = grad_cube[i,j,k]
                token = density_to_token(rho, grad)
                token_cube[i,j,k] = token
                state_cube[i,j,k] = int(token[:3], 2)   # vertex bits only
    return state_cube, token_cube

# ----------------------------------------------------------------------
# 4. Fourier cube hash (rotation‑invariant)
# ----------------------------------------------------------------------
def cube_fourier_hash(cube):
    """Return rotation‑invariant hash of a 3D cube (numpy array)."""
    f = np.fft.fftn(cube)
    mag = np.abs(f)
    # Quantize to 4 decimal places and return tuple
    quantized = np.round(mag.flatten(), 4)
    return tuple(quantized)

def is_rotationally_symmetric(cube):
    """Check if cube is symmetric under any non‑trivial rotation."""
    # Simple test: compare hash with rotations (full verification would be expensive)
    # Here we just check a few rotations: 90° around x, y, z
    original_hash = cube_fourier_hash(cube)
    for axis in (0,1,2):
        for k in (1,2,3):
            rot = np.rot90(cube, k, axes=(axis, (axis+1)%3))
            if cube_fourier_hash(rot) == original_hash:
                return True
    return False

# ----------------------------------------------------------------------
# 5. Main demo for H₂ and CH₄
# ----------------------------------------------------------------------
def demo_h2():
    print("=" * 60)
    print("H₂ Molecule")
    print("=" * 60)
    # Coordinates (Å)
    coords = [(0,0,0), (0.74,0,0)]   # H–H bond along x-axis
    charges = [1, 1]
    side = 8   # cube resolution
    state_cube, token_cube = molecule_to_token_cube(coords, charges, side=side)
    print(f"State cube shape: {state_cube.shape}")
    print("First few tokens at center slice (z=0):")
    mid = side//2
    for i in range(side):
        row = [token_cube[i,j,mid] for j in range(side)]
        print(" ".join(row[:6]) + " ...")
    # Check symmetry
    symmetric = is_rotationally_symmetric(state_cube)
    print(f"\nCube rotationally symmetric? {symmetric}")
    # Expected: symmetric under 180° rotation around y or z axis (due to H₂ linear)
    # Also symmetric under 180° around x? No, because bond is along x, so 180° around x swaps the atoms? Actually atoms are identical, so yes.
    print("(Expected: symmetric under 180° around any axis perpendicular to bond)")

def demo_ch4():
    print("\n" + "=" * 60)
    print("CH₄ (Methane) Molecule")
    print("=" * 60)
    # Tetrahedral coordinates (carbon at origin, hydrogens at corners of a cube)
    # Standard: H at (1,1,1), (1,-1,-1), (-1,1,-1), (-1,-1,1) scaled by 0.6 Å
    scale = 0.6
    coords = [(0,0,0)] + [(scale, scale, scale), (scale, -scale, -scale),
                          (-scale, scale, -scale), (-scale, -scale, scale)]
    charges = [6, 1, 1, 1, 1]   # carbon + 4 hydrogens
    side = 10
    state_cube, token_cube = molecule_to_token_cube(coords, charges, side=side)
    print(f"State cube shape: {state_cube.shape}")
    symmetric = is_rotationally_symmetric(state_cube)
    print(f"Cube rotationally symmetric? {symmetric}")
    print("(Expected: high symmetry – tetrahedral group, many rotational symmetries)")

if __name__ == "__main__":
    demo_h2()
    demo_ch4()
