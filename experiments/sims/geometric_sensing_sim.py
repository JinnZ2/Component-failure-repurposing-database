#!/usr/bin/env python3
"""
Real-time Geometric Sensing via 3D Cube
========================================
Reads accelerometer data from phone (Termux), converts each reading to an
octahedral token, accumulates tokens into a 3D cube, and detects when the
cube cancels (dependency found) -- indicating a repeated or symmetric gesture.

Enhanced with components adapted from the GEIS (Geometric Information Encoding
System) library:
  - OctahedralState: full vertex algebra with inversion, distance, dot product
  - GeometricEncoder: bidirectional token <-> binary encoding
  - StateTensor: 3x3 symmetric tensor fingerprints for cancellation detection
  - Tensor dependency search: finds subsets whose tensors sum to near-zero

Source: github.com/JinnZ2/Geometric-to-Binary-Computational-Bridge/tree/main/GEIS

Requires: numpy
"""

import subprocess
import json
import time
import math
import numpy as np
from collections import deque, defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import List, Tuple, Optional, Dict


# ======================================================================
# GEIS Core — OctahedralState
# Adapted from GEIS/octahedral_state.py
# ======================================================================

class OctahedralState:
    """
    One of 8 vertices of an octahedron (cube vertices on unit sphere).

    Vertex positions are (+-1, +-1, +-1) / sqrt(3), indexed 0-7.
    Provides geometric operations: inversion (NOT), distance, dot product,
    and token/binary conversion.
    """

    # 8 vertex positions normalised to unit sphere
    POSITIONS = []
    for _ix in (-1, 1):
        for _iy in (-1, 1):
            for _iz in (-1, 1):
                _v = np.array([_ix, _iy, _iz], dtype=float)
                _v /= np.linalg.norm(_v)
                POSITIONS.append(_v)

    def __init__(self, index: int):
        if not isinstance(index, int) or not (0 <= index <= 7):
            raise ValueError("Index must be integer 0-7")
        self.index = index
        self.position = self.POSITIONS[index]

    def to_binary(self, width: int = 3) -> str:
        return format(self.index, f'0{width}b')

    def to_token(self, operator: str = '|', symbol: str = 'O') -> str:
        return f"{self.to_binary()}{operator}{symbol}"

    @classmethod
    def from_token(cls, token: str) -> 'OctahedralState':
        for op in ['||', '|', '/', ':']:
            if op in token:
                parts = token.split(op, 1)
                return cls(int(parts[0], 2))
        raise ValueError("Token must contain operator ('|', '/', ':')")

    @classmethod
    def closest(cls, vec: np.ndarray) -> 'OctahedralState':
        """Find state whose position is closest to given direction vector."""
        norm = np.linalg.norm(vec)
        if norm < 1e-12:
            return cls(0)
        vec = vec / norm
        dots = [np.dot(vec, pos) for pos in cls.POSITIONS]
        return cls(int(np.argmax(dots)))

    def invert(self) -> 'OctahedralState':
        """Octahedral inversion (NOT): i -> (7 - i)."""
        return OctahedralState(7 - self.index)

    def distance_to(self, other: 'OctahedralState') -> float:
        return float(np.linalg.norm(self.position - other.position))

    def dot_product(self, other: 'OctahedralState') -> float:
        return float(np.dot(self.position, other.position))

    def __eq__(self, other) -> bool:
        return isinstance(other, OctahedralState) and self.index == other.index

    def __hash__(self) -> int:
        return hash(self.index)

    def __repr__(self) -> str:
        return f"O{self.index}@{self.to_binary()}"


# ======================================================================
# GEIS Core — GeometricEncoder
# Adapted from GEIS/geometric_encoder.py
# ======================================================================

class GeometricEncoder:
    """
    Bidirectional encoder between geometric tokens and flat binary.

    Token format: <vertex_bits><operator><symbol>
      vertex_bits: 3-bit binary (000-111)
      operator:    | (radial, 1 bit=1) or / (tangential, 1 bit=0)
                   || (nested, 2 bits=11)
      symbol:      O=00, I=01, X=10, delta=11
    """

    SYMBOL_MAP = {'O': '00', 'I': '01', 'X': '10', '\u0394': '11'}
    REVERSE_SYMBOL_MAP = {v: k for k, v in SYMBOL_MAP.items()}
    OPERATOR_MAP = {'|': '1', '/': '0', ':': '0'}
    REVERSE_OPERATOR_MAP = {'1': '|', '0': '/'}

    def __init__(self, vertex_width: int = 3):
        self.vertex_width = vertex_width

    def encode_to_binary(self, token: str) -> str:
        if '||' in token:
            parts = token.split('||', 1)
            vertex_bits = parts[0]
            symbol = parts[1][0] if parts[1] else 'O'
            operator_bits = '11'
        else:
            op = next((o for o in ['|', '/', ':'] if o in token), None)
            if op is None:
                raise ValueError("No operator found in token")
            parts = token.split(op, 1)
            vertex_bits = parts[0]
            symbol = parts[1][0] if parts[1] else 'O'
            operator_bits = self.OPERATOR_MAP[op]
        if len(vertex_bits) != self.vertex_width:
            raise ValueError(f"Vertex bits must be {self.vertex_width} wide")
        symbol_bits = self.SYMBOL_MAP.get(symbol)
        if symbol_bits is None:
            raise ValueError(f"Unknown symbol '{symbol}'")
        return vertex_bits + operator_bits + symbol_bits

    def decode_from_binary(self, binary_string: str) -> str:
        vertex_bits = binary_string[:self.vertex_width]
        pos = self.vertex_width
        if (len(binary_string) >= pos + 4
                and binary_string[pos:pos + 2] == '11'):
            operator = '||'
            symbol_bits = binary_string[pos + 2:pos + 4]
        else:
            operator = self.REVERSE_OPERATOR_MAP.get(
                binary_string[pos], '|')
            symbol_bits = binary_string[pos + 1:pos + 3]
        symbol = self.REVERSE_SYMBOL_MAP.get(symbol_bits, 'O')
        return f"{vertex_bits}{operator}{symbol}"

    def get_components(self, token: str) -> Tuple[str, str, str]:
        for op in ['||', '|', '/']:
            if op in token:
                parts = token.split(op, 1)
                symbol = parts[1][0] if parts[1] else 'O'
                return parts[0], op, symbol
        raise ValueError("Invalid token format")


# ======================================================================
# GEIS Core — StateTensor
# Adapted from GEIS/state_tensor.py
# ======================================================================

class StateTensor:
    """
    3x3 symmetric tensor (v x v) representing a geometric fingerprint.

    Used to detect cancellations: when a subset of tensors sums to
    near-zero, the corresponding tokens form a geometric dependency.
    """

    def __init__(self, state: OctahedralState, weight: float = 1.0):
        self.state = state
        self.weight = weight
        self.vector = state.position
        v = self.vector * weight
        self.tensor = np.outer(v, v)

    def project(self, direction) -> float:
        """Scalar projection: n-hat . T . n-hat"""
        n = np.array(direction, dtype=float)
        n = n / np.linalg.norm(n)
        return float(n @ self.tensor @ n)

    def eigenvalues(self) -> np.ndarray:
        return np.linalg.eigvalsh(self.tensor)

    def trace(self) -> float:
        return float(np.trace(self.tensor))

    def norm(self) -> float:
        return float(np.linalg.norm(self.tensor))

    @staticmethod
    def combine(tensors: List['StateTensor']) -> np.ndarray:
        combined = np.zeros((3, 3))
        for t in tensors:
            combined += t.tensor
        return combined


# ======================================================================
# Token generation — accelerometer vector -> geometric token
# ======================================================================

def vector_to_token(x: float, y: float, z: float,
                    phase: float = 0.0) -> str:
    """
    Convert acceleration vector (x, y, z) and phase angle to a
    geometric token.

    Phase mapping (degrees):
      0   -> O (Octahedral)
      90  -> I (Inversion)
      180 -> X (Exchange)
      270 -> delta (Delta)
    """
    direction = np.array([x, y, z])
    norm = np.linalg.norm(direction)
    if norm < 1e-6:
        direction = np.array([0.0, 0.0, 1.0])
        norm = 1.0

    state = OctahedralState.closest(direction)
    vertex_bits = state.to_binary()

    # Operator: radial if aligned with (1,1,1) diagonal, else tangential
    radial_axis = np.array([1, 1, 1]) / math.sqrt(3)
    dot = abs(np.dot(direction / norm, radial_axis))
    operator = '|' if dot > 0.7 else '/'

    # Symbol from phase
    phase_norm = (phase % 360) / 90.0
    symbol_idx = int(round(phase_norm)) % 4
    symbol = ['O', 'I', 'X', '\u0394'][symbol_idx]

    return f"{vertex_bits}{operator}{symbol}"


# ======================================================================
# Tensor-based token helpers
# ======================================================================

def token_to_tensor(token: str) -> np.ndarray:
    """Convert token to 3x3 symmetric tensor (outer product of vertex)."""
    idx = int(token[:3], 2)
    v = OctahedralState.POSITIONS[idx]
    return np.outer(v, v)


def tensor_norm(T: np.ndarray) -> float:
    return float(np.linalg.norm(T))


def tensor_sum(tensors: List[np.ndarray]) -> np.ndarray:
    return sum(tensors, np.zeros((3, 3)))


# ======================================================================
# 3D Cube from token stream
# ======================================================================

def tokens_to_cube(tokens: List[str], side: int) -> np.ndarray:
    """
    Fill a 3D cube of shape (side, side, side) with 3-bit vertex states.
    Each token's vertex bits become a voxel value (0-7).
    """
    cube = np.zeros((side, side, side), dtype=np.uint8)
    idx = 0
    for i in range(side):
        for j in range(side):
            for k in range(side):
                if idx < len(tokens):
                    cube[i, j, k] = int(tokens[idx][:3], 2)
                idx += 1
    return cube


def cube_to_hash(cube: np.ndarray) -> bytes:
    """Unique hash for cube state (used for exact-match detection)."""
    return cube.tobytes()


def cube_xor(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pointwise XOR of two cubes."""
    return a ^ b


def cube_norm(cube: np.ndarray) -> int:
    """Number of nonzero voxels (L0 norm)."""
    return int(np.count_nonzero(cube))


# ======================================================================
# Dependency detection — dual mode (cube + tensor)
# ======================================================================

def find_cube_dependencies(cubes: List[np.ndarray]) -> List[Tuple[int, int]]:
    """
    Exact-match: two cubes that are identical (XOR to zero).
    Returns list of (i, j) pairs.
    """
    n = len(cubes)
    deps = []
    for i in range(n):
        for j in range(i + 1, n):
            if np.array_equal(cubes[i], cubes[j]):
                deps.append((i, j))
    return deps


def find_tensor_dependencies(tokens: List[str],
                             max_len: int = 4) -> List[List[int]]:
    """
    Find subsets of token indices whose tensors sum to near-zero
    (Frobenius norm < 1e-6).  Uses brute force for pairs/triples and
    meet-in-the-middle for quadruples.

    Adapted from GEIS/geometric_sensor_sim.py find_dependencies().
    """
    tensors = [token_to_tensor(tok) for tok in tokens]
    n = len(tokens)
    deps: List[List[int]] = []

    # Pairs
    for i in range(n):
        for j in range(i + 1, n):
            if tensor_norm(tensors[i] + tensors[j]) < 1e-6:
                deps.append([i, j])

    # Triples (brute force, small n only)
    if max_len >= 3 and n <= 200:
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    if tensor_norm(tensors[i] + tensors[j]
                                   + tensors[k]) < 1e-6:
                        deps.append([i, j, k])

    # Meet-in-the-middle for quadruples
    if max_len >= 4 and n <= 500:
        half = n // 2
        sum_map: Dict[Tuple[float, ...],
                       List[Tuple[int, ...]]] = defaultdict(list)
        for length in range(1, max_len // 2 + 1):
            for combo in combinations(range(half), length):
                S = tensor_sum([tensors[i] for i in combo])
                key = tuple(np.round(S.flatten(), decimals=10))
                sum_map[key].append(combo)
        for length in range(1, max_len - max_len // 2 + 1):
            for combo in combinations(range(half, n), length):
                S = tensor_sum([tensors[i] for i in combo])
                target = tuple(np.round((-S).flatten(), decimals=10))
                if target in sum_map:
                    for first in sum_map[target]:
                        combined = list(first) + list(combo)
                        if len(combined) <= max_len:
                            deps.append(combined)

    # Deduplicate
    seen = set()
    unique = []
    for dep in deps:
        key = tuple(sorted(dep))
        if key not in seen:
            seen.add(key)
            unique.append(dep)
    return unique


# ======================================================================
# Sensor reading (Termux)
# ======================================================================

def read_accelerometer(samples: int = 10,
                       delay_ms: int = 100
                       ) -> List[Tuple[float, float, float]]:
    """
    Run termux-sensor and return list of (x, y, z) acceleration readings.
    """
    cmd = ["termux-sensor", "-s", "android.sensor.accelerometer",
           "-d", str(delay_ms), "-n", str(samples)]
    try:
        output = subprocess.check_output(
            cmd, stderr=subprocess.DEVNULL).decode()
        data = json.loads(output)
        sensor_data = data.get("android.sensor.accelerometer", {})
        values = sensor_data.get("values", [])
        return [(float(v[0]), float(v[1]), float(v[2]))
                for v in values if len(v) >= 3]
    except Exception:
        return []


# ======================================================================
# Main real-time loop
# ======================================================================

def main():
    print("=" * 70)
    print("REAL GEOMETRIC SENSING via 3D CUBE")
    print("Accelerometer -> octahedral tokens -> 3D cube -> dependencies")
    print("Enhanced with GEIS tensor analysis")
    print("=" * 70)

    encoder = GeometricEncoder()

    # Cube parameters
    CUBE_SIDE = 4           # 4x4x4 = 64 tokens per cube
    BUFFER_SIZE = CUBE_SIDE ** 3
    SENSOR_SAMPLES = 20     # samples per iteration
    SENSOR_DELAY_MS = 50    # 50 ms between samples -> 20 Hz

    token_buffer: deque = deque(maxlen=BUFFER_SIZE)
    cubes_history: List[np.ndarray] = []
    token_history: List[List[str]] = []  # parallel token lists per cube
    last_print = time.time()
    phase_counter = 0.0     # simple phase ramp for demo

    print(f"\nCollecting tokens into {CUBE_SIDE}x{CUBE_SIDE}x{CUBE_SIDE} "
          f"cubes ({BUFFER_SIZE} tokens each)...")
    print("Move your phone! Dependencies detected via cube match AND "
          "tensor cancellation.\n")

    # Show encoder example
    sample_token = vector_to_token(0.5, 0.3, 0.8, phase=45.0)
    sample_binary = encoder.encode_to_binary(sample_token)
    print(f"  Example: vector(0.5, 0.3, 0.8) phase=45 -> "
          f"token '{sample_token}' -> binary '{sample_binary}'")
    state = OctahedralState.from_token(sample_token)
    inv = state.invert()
    print(f"  State {state} inverts to {inv} "
          f"(distance {state.distance_to(inv):.3f})")
    T = StateTensor(state)
    print(f"  Tensor trace={T.trace():.4f}  norm={T.norm():.4f}  "
          f"eigenvalues={np.round(T.eigenvalues(), 4)}")
    print()

    sim_warned = False

    try:
        while True:
            # Get fresh accelerometer readings
            readings = read_accelerometer(
                samples=SENSOR_SAMPLES, delay_ms=SENSOR_DELAY_MS)

            if not readings:
                # Fallback: simulate random motion if sensor unavailable
                readings = [
                    (np.random.uniform(-1, 1),
                     np.random.uniform(-1, 1),
                     np.random.uniform(-1, 1))
                    for _ in range(5)
                ]
                if not sim_warned:
                    print("No sensor data. Simulating random vectors "
                          "for demo.")
                    sim_warned = True

            for x, y, z in readings:
                token = vector_to_token(x, y, z, phase=phase_counter)
                phase_counter = (phase_counter + 15.0) % 360.0
                token_buffer.append(token)

                # When buffer full, form a cube
                if len(token_buffer) == BUFFER_SIZE:
                    token_list = list(token_buffer)
                    cube = tokens_to_cube(token_list, CUBE_SIDE)

                    # --- Cube-level duplicate detection ---
                    cube_dep_found = False
                    for idx, prev_cube in enumerate(cubes_history):
                        if np.array_equal(cube, prev_cube):
                            print(f"\n  CUBE DEPENDENCY: repeats "
                                  f"history[{idx}]")
                            xor = cube_xor(cube, prev_cube)
                            print(f"    XOR norm = {cube_norm(xor)} "
                                  f"(geometric cancellation)")
                            cube_dep_found = True
                            break

                    # --- Tensor cancellation across recent tokens ---
                    # Check the current cube's tokens for internal deps
                    tensor_deps = find_tensor_dependencies(
                        token_list, max_len=3)
                    if tensor_deps:
                        print(f"\n  TENSOR DEPENDENCY in current cube: "
                              f"{len(tensor_deps)} cancellation(s)")
                        for dep in tensor_deps[:3]:
                            toks = [token_list[i] for i in dep]
                            T_sum = tensor_sum(
                                [token_to_tensor(t) for t in toks])
                            print(f"    indices {dep} -> tokens {toks} "
                                  f"-> sum norm {tensor_norm(T_sum):.2e}")

                    # Store history (keep last 10)
                    cubes_history.append(cube)
                    token_history.append(token_list)
                    if len(cubes_history) > 10:
                        cubes_history.pop(0)
                        token_history.pop(0)

                    token_buffer.clear()

                    # Heartbeat
                    now = time.time()
                    if now - last_print >= 2:
                        vertex, op, sym = encoder.get_components(
                            token_list[-1])
                        print(f"  New cube #{len(cubes_history):>3} | "
                              f"last token: {token_list[-1]} "
                              f"(v={vertex} op={op} sym={sym}) | "
                              f"{'CUBE DEP' if cube_dep_found else 'ok'}")
                        last_print = now

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nStopped. Summary:")
        print(f"  Cubes formed: {len(cubes_history)}")
        total_tokens = sum(len(tl) for tl in token_history)
        print(f"  Tokens processed: {total_tokens}")

        # Final cross-cube tensor analysis
        if token_history:
            all_tokens = [t for tl in token_history for t in tl]
            sample = all_tokens[:min(100, len(all_tokens))]
            deps = find_tensor_dependencies(sample, max_len=4)
            print(f"  Tensor dependencies (last {len(sample)} tokens): "
                  f"{len(deps)}")

        print("Goodbye!")


if __name__ == "__main__":
    main()
