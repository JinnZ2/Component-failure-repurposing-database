#!/usr/bin/env python3
"""
Geometric Failure Diagnosis
===========================
Maps component failure modes to octahedral tokens, simulates degradation,
and detects repeated patterns (dependencies) via 3D cube cancellation.
Also demonstrates AI self-diagnosis via internal state cubes.

**Database interaction:** Loads real failure modes, repurpose options,
environmental interactions, synergies, and redundancy channel data from
the CSV matrices in ``matrices/``.  Token generation is driven by actual
database rows rather than hardcoded values.

Requires: numpy

Source GEIS classes: geometric_sensing_sim.py (sibling module)
"""

import csv
import hashlib
import os
import random
import sys
import time
from collections import deque
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

# -- Locate repo root (matrices/ lives there) --------------------------
REPO_ROOT = _HERE.parent.parent
MATRICES_DIR = REPO_ROOT / "matrices"


# ======================================================================
# Database loaders
# ======================================================================

@dataclass
class FailureModeRow:
    component: str
    failure_mode: str
    repurpose_option: str
    effectiveness: str        # High / Medium / Low
    notes: str = ""


@dataclass
class RepurposeRow:
    component: str
    failure_mode: str
    application: str
    effectiveness: str
    notes: str = ""


@dataclass
class EnvironmentalRow:
    component: str
    condition: str
    observed_effect: str
    repurpose_impact: str
    notes: str = ""


@dataclass
class SynergyRow:
    comp_a: str
    comp_b: str
    synergy_effect: str
    application: str
    notes: str = ""


@dataclass
class RedundancyChannelRow:
    component: str
    failure_mode: str
    channel: str
    method: str
    notes: str = ""
    glyphs: str = ""


@dataclass
class DecayRow:
    channel: str
    condition: str
    degradation_pattern: str
    residual: str
    notes: str = ""
    glyphs: str = ""


def _load_csv(path: Path, row_cls, field_count: int) -> list:
    """Generic CSV loader — skips header, strips whitespace, ignores blanks."""
    rows = []
    if not path.exists():
        print(f"  Warning: {path.name} not found, skipping")
        return rows
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for line in reader:
            line = [c.strip() for c in line]
            if not line or not line[0]:
                continue
            # Pad short rows
            while len(line) < field_count:
                line.append("")
            rows.append(row_cls(*line[:field_count]))
    return rows


class DatabaseInterface:
    """
    Reads the repository's CSV matrices into structured objects.
    Provides lookup helpers used by the diagnosis engine.
    """

    def __init__(self, matrices_dir: Path = MATRICES_DIR):
        self.matrices_dir = matrices_dir
        self.failure_modes: List[FailureModeRow] = []
        self.repurpose: List[RepurposeRow] = []
        self.environmental: List[EnvironmentalRow] = []
        self.synergies: List[SynergyRow] = []
        self.channels: List[RedundancyChannelRow] = []
        self.decay: List[DecayRow] = []
        self._load()

    def _load(self) -> None:
        print(f"Loading database from {self.matrices_dir} ...")
        self.failure_modes = _load_csv(
            self.matrices_dir / "failure_mode_matrix.csv",
            FailureModeRow, 5)
        self.repurpose = _load_csv(
            self.matrices_dir / "repurpose_effectiveness.csv",
            RepurposeRow, 5)
        self.environmental = _load_csv(
            self.matrices_dir / "environmental_interactions.csv",
            EnvironmentalRow, 5)
        self.synergies = _load_csv(
            self.matrices_dir / "component_synergies.csv",
            SynergyRow, 5)
        self.channels = _load_csv(
            self.matrices_dir / "redundancy_channels.csv",
            RedundancyChannelRow, 6)
        self.decay = _load_csv(
            self.matrices_dir / "redundancy_decay.csv",
            DecayRow, 6)
        total = (len(self.failure_modes) + len(self.repurpose)
                 + len(self.environmental) + len(self.synergies)
                 + len(self.channels) + len(self.decay))
        print(f"  Loaded {total} rows across 6 matrices")
        print(f"    failure_modes:   {len(self.failure_modes)}")
        print(f"    repurpose:       {len(self.repurpose)}")
        print(f"    environmental:   {len(self.environmental)}")
        print(f"    synergies:       {len(self.synergies)}")
        print(f"    channels:        {len(self.channels)}")
        print(f"    decay:           {len(self.decay)}")

    # -- Lookup helpers -------------------------------------------------

    def modes_for(self, component: str) -> List[FailureModeRow]:
        """Return all failure modes whose component field contains *component*."""
        c = component.lower()
        return [r for r in self.failure_modes if c in r.component.lower()]

    def repurpose_for(self, component: str,
                      mode: str = "") -> List[RepurposeRow]:
        c = component.lower()
        m = mode.lower()
        return [r for r in self.repurpose
                if c in r.component.lower()
                and (not m or m in r.failure_mode.lower())]

    def env_for(self, component: str) -> List[EnvironmentalRow]:
        c = component.lower()
        return [r for r in self.environmental if c in r.component.lower()]

    def synergies_for(self, component: str) -> List[SynergyRow]:
        c = component.lower()
        return [r for r in self.synergies
                if c in r.comp_a.lower() or c in r.comp_b.lower()]

    def channels_for(self, component: str) -> List[RedundancyChannelRow]:
        c = component.lower()
        return [r for r in self.channels if c in r.component.lower()]

    def decay_for(self, channel: str) -> List[DecayRow]:
        ch = channel.lower()
        return [r for r in self.decay if ch in r.channel.lower()]

    def all_components(self) -> List[str]:
        """Unique component names from the failure mode matrix."""
        seen = []
        for r in self.failure_modes:
            if r.component not in seen:
                seen.append(r.component)
        return seen

    def all_failure_modes(self) -> List[Tuple[str, str]]:
        """All (component, failure_mode) pairs."""
        return [(r.component, r.failure_mode) for r in self.failure_modes]


# ======================================================================
# Token generation from database rows
# ======================================================================

EFFECTIVENESS_SYMBOL = {"High": "O", "Medium": "I", "Low": "X"}
SEVERITY_OPERATOR = {"abrupt": "|", "gradual": "/", "intermittent": "||"}


def failure_to_token(component: str, failure_mode: str,
                     severity: str = "gradual",
                     effectiveness: str = "Medium") -> str:
    """
    Map a database failure record to a deterministic geometric token.

    - vertex: hash(component:mode) mod 8  -> 3-bit address
    - operator: severity  -> | (abrupt) / (gradual) || (intermittent)
    - symbol: repurpose effectiveness -> O (High) I (Medium) X (Low)
              or delta if unknown
    """
    key = f"{component}:{failure_mode}"
    h = int(hashlib.md5(key.encode()).hexdigest()[:2], 16) % 8
    vertex = f"{h:03b}"
    operator = SEVERITY_OPERATOR.get(severity, "/")
    symbol = EFFECTIVENESS_SYMBOL.get(effectiveness, "\u0394")
    return f"{vertex}{operator}{symbol}"


def row_to_token(row: FailureModeRow,
                 severity: str = "gradual") -> str:
    """Convert a FailureModeRow directly to a token."""
    return failure_to_token(row.component, row.failure_mode,
                            severity, row.effectiveness)


# ======================================================================
# 3D Cube helpers
# ======================================================================

def tokens_to_cube(tokens: List[str], side: int = 4) -> np.ndarray:
    cube = np.zeros((side, side, side), dtype=np.uint8)
    idx = 0
    for i in range(side):
        for j in range(side):
            for k in range(side):
                if idx < len(tokens):
                    cube[i, j, k] = int(tokens[idx][:3], 2)
                idx += 1
    return cube


def find_repeated_cube(cubes_history: List[np.ndarray]
                       ) -> Tuple[bool, int]:
    if len(cubes_history) < 2:
        return False, -1
    latest = cubes_history[-1]
    for i, prev in enumerate(cubes_history[:-1]):
        if np.array_equal(latest, prev):
            return True, i
    return False, -1


# ======================================================================
# Degradation simulator (driven by database)
# ======================================================================

def simulate_degradation(db: DatabaseInterface,
                         component: str,
                         duration_sec: float = 20,
                         rate_hz: float = 4):
    """
    Yield geometric tokens as *component* degrades over time.

    Pulls real failure modes from the database. Severity escalates
    from gradual -> intermittent -> abrupt.  Repurpose effectiveness
    from the database determines the token symbol.
    """
    modes = db.modes_for(component)
    if not modes:
        print(f"  No failure modes found for '{component}', using generic")
        modes = [FailureModeRow(component, "generic_degradation",
                                "Unknown", "Low", "")]

    start = time.time()
    end = start + duration_sec
    while time.time() < end:
        t = (time.time() - start) / duration_sec
        # Failure probability ramps up
        if random.random() < 0.05 + t * 0.8:
            row = random.choices(
                modes,
                weights=[1 + t * 2] * len(modes))[0]
            if t < 0.3:
                severity = "gradual"
            elif t < 0.7:
                severity = "intermittent"
            else:
                severity = "abrupt"
            token = row_to_token(row, severity)
            yield token, row, severity
        time.sleep(1.0 / rate_hz)


# ======================================================================
# AI self-diagnosis via internal-state cubes
# ======================================================================

def internal_state_token(metric: str, value: float,
                         thresholds: Tuple[float, float]) -> str:
    """Map an internal metric to a token."""
    lo, hi = thresholds
    span = hi - lo if hi != lo else 1.0
    norm = min(1.0, max(0.0, (value - lo) / span))
    vertex = f"{int(norm * 7):03b}"
    operator = "|" if value < lo or value > hi else "/"
    sym_idx = int((value * 10) % 4)
    symbol = ["O", "I", "X", "\u0394"][sym_idx]
    return f"{vertex}{operator}{symbol}"


def ai_self_diagnose(interval_sec: float = 3, cube_side: int = 3,
                     iterations: int = 8):
    """
    Periodically sample simulated internal metrics, build cubes,
    and detect repeated patterns (self-diagnosis).
    Runs for *iterations* rounds (not infinite).
    """
    metrics_config = {
        "cpu_usage":        (20.0, 70.0),
        "memory_usage":     (30.0, 75.0),
        "response_latency": (10.0, 100.0),
        "error_rate":       (0.0, 2.0),
    }
    token_buffer: deque = deque(maxlen=cube_side ** 3)
    cubes_history: List[np.ndarray] = []

    print("\nAI Self-Diagnosis active. Watching for repeated state cubes...")
    for iteration in range(iterations):
        fake_values = {
            "cpu_usage":        random.uniform(10, 90),
            "memory_usage":     random.uniform(20, 80),
            "response_latency": random.uniform(5, 200),
            "error_rate":       random.uniform(0, 5),
        }
        for metric, thresh in metrics_config.items():
            token = internal_state_token(metric, fake_values[metric], thresh)
            token_buffer.append(token)
            if len(token_buffer) == cube_side ** 3:
                cube = tokens_to_cube(list(token_buffer), cube_side)
                cubes_history.append(cube)
                repeated, idx = find_repeated_cube(cubes_history)
                if repeated:
                    print(f"  Self-diagnosis: cube repeated "
                          f"(match with cube {idx})")
                    print(f"    -> System may be in a failure/recovery cycle")
                cubes_history = cubes_history[-10:]
        if iteration < iterations - 1:
            time.sleep(interval_sec)


# ======================================================================
# Demo — full database-interactive diagnosis
# ======================================================================

def demo():
    print("=" * 70)
    print("GEOMETRIC FAILURE DIAGNOSIS")
    print("Octahedral tokens + 3D cube cancellation + database interaction")
    print("=" * 70)

    db = DatabaseInterface()
    encoder = GeometricEncoder()

    # -- Show available components from the database --------------------
    components = db.all_components()
    print(f"\nComponents in database: {components}")

    all_modes = db.all_failure_modes()
    print(f"Total (component, failure_mode) pairs: {len(all_modes)}")

    # -- Token mapping for every database row --------------------------
    print(f"\n{'Component':<22} {'Failure Mode':<22} {'Repurpose':<22} "
          f"{'Eff':>4}  {'Token':<10} {'Binary':<8}")
    print("-" * 95)
    for row in db.failure_modes:
        token = row_to_token(row, "gradual")
        binary = encoder.encode_to_binary(token)
        print(f"{row.component:<22} {row.failure_mode:<22} "
              f"{row.repurpose_option:<22} {row.effectiveness:>4}  "
              f"{token:<10} {binary:<8}")

    # -- Environmental context -----------------------------------------
    print(f"\nEnvironmental interactions ({len(db.environmental)} rows):")
    for row in db.environmental[:5]:
        token = failure_to_token(row.component, row.condition,
                                 "gradual", "Medium")
        print(f"  {row.component:<20} {row.condition:<25} -> {token}  "
              f"({row.repurpose_impact})")
    if len(db.environmental) > 5:
        print(f"  ... and {len(db.environmental) - 5} more")

    # -- Synergy pairs -------------------------------------------------
    print(f"\nSynergy pairs ({len(db.synergies)} rows):")
    for row in db.synergies[:5]:
        tok_a = failure_to_token(row.comp_a, "synergy", "gradual", "Medium")
        tok_b = failure_to_token(row.comp_b, "synergy", "gradual", "Medium")
        T_a = token_to_tensor(tok_a)
        T_b = token_to_tensor(tok_b)
        combined_norm = tensor_norm(T_a + T_b)
        print(f"  {row.comp_a:<30} + {row.comp_b:<30}")
        print(f"    tokens: {tok_a} + {tok_b}  "
              f"tensor sum norm: {combined_norm:.4f}")
        print(f"    -> {row.application}")
    if len(db.synergies) > 5:
        print(f"  ... and {len(db.synergies) - 5} more")

    # -- Redundancy channels -------------------------------------------
    print(f"\nRedundancy channels ({len(db.channels)} rows):")
    for row in db.channels:
        token = failure_to_token(row.component, row.failure_mode,
                                 "gradual", "Medium")
        print(f"  {row.glyphs}  {row.component:<28} {row.failure_mode:<20} "
              f"-> {row.channel:<18} token: {token}")

    # -- Channel decay tensor analysis ---------------------------------
    print(f"\nChannel decay ({len(db.decay)} rows) — tensor fingerprints:")
    decay_tokens = []
    for row in db.decay:
        token = failure_to_token(row.channel, row.condition,
                                 "gradual", "Medium")
        decay_tokens.append(token)
        state = OctahedralState.from_token(token)
        T = StateTensor(state)
        print(f"  {row.channel:<20} {row.condition:<25} "
              f"token: {token}  trace: {T.trace():.4f}  "
              f"norm: {T.norm():.4f}")

    # Search for tensor dependencies across all decay tokens
    if len(decay_tokens) >= 2:
        deps = find_tensor_dependencies(decay_tokens, max_len=3)
        if deps:
            print(f"\n  Tensor dependencies found across decay tokens: "
                  f"{len(deps)}")
            for dep in deps[:3]:
                toks = [decay_tokens[i] for i in dep]
                print(f"    indices {dep} -> {toks}")
        else:
            print(f"\n  No tensor cancellations in decay tokens "
                  f"(all modes geometrically distinct)")

    # -- Live degradation simulation -----------------------------------
    # Pick the first component that has modes
    target = components[0] if components else "Diode"
    target_modes = db.modes_for(target)
    target_repurpose = db.repurpose_for(target)

    print(f"\n{'=' * 70}")
    print(f"Simulating degradation of: {target}")
    print(f"  Known failure modes:  {[r.failure_mode for r in target_modes]}")
    print(f"  Repurpose options:    {len(target_repurpose)}")
    for rp in target_repurpose:
        print(f"    {rp.failure_mode:<22} -> {rp.application:<28} "
              f"({rp.effectiveness})")
    print(f"{'=' * 70}")

    token_buffer: deque = deque(maxlen=64)
    cubes_history: List[np.ndarray] = []
    all_tokens: List[str] = []
    severity_counts: Dict[str, int] = {
        "gradual": 0, "intermittent": 0, "abrupt": 0}
    mode_counts: Dict[str, int] = {}

    for token, row, severity in simulate_degradation(
            db, target, duration_sec=15, rate_hz=4):
        all_tokens.append(token)
        severity_counts[severity] += 1
        mode_counts[row.failure_mode] = mode_counts.get(
            row.failure_mode, 0) + 1

        token_buffer.append(token)
        if len(token_buffer) == 64:
            cube = tokens_to_cube(list(token_buffer), side=4)
            cubes_history.append(cube)
            repeated, idx = find_repeated_cube(cubes_history)
            if repeated:
                print(f"\n  DEPENDENCY: cube repeats pattern from "
                      f"cube #{idx}")
                print(f"    -> Failure signature has become periodic")
                print(f"    -> Geometric cancellation implies "
                      f"predictable cascade")
                # Look up what repurpose is viable at this stage
                for rp in target_repurpose:
                    print(f"    -> Repurpose: {rp.application} "
                          f"({rp.effectiveness})")
            else:
                print(f"  New cube #{len(cubes_history)} formed "
                      f"({len(all_tokens)} tokens total)")
            cubes_history = cubes_history[-10:]
            token_buffer.clear()

    # -- Post-simulation tensor analysis --------------------------------
    print(f"\nDegradation summary:")
    print(f"  Total tokens: {len(all_tokens)}")
    print(f"  Severity: {dict(severity_counts)}")
    print(f"  Mode distribution: {dict(mode_counts)}")

    if len(all_tokens) >= 4:
        sample = all_tokens[:min(100, len(all_tokens))]
        deps = find_tensor_dependencies(sample, max_len=4)
        print(f"  Tensor dependencies in token stream: {len(deps)}")
        for dep in deps[:3]:
            toks = [sample[i] for i in dep]
            states = [OctahedralState.from_token(t) for t in toks]
            print(f"    {dep} -> {toks}")
            for s in states:
                inv = s.invert()
                print(f"      {s} inverts to {inv}  "
                      f"(distance {s.distance_to(inv):.3f})")

    # -- Cross-component synergy check ---------------------------------
    target_synergies = db.synergies_for(target)
    if target_synergies:
        print(f"\n  Synergies involving {target}:")
        for syn in target_synergies:
            print(f"    + {syn.comp_b if target.lower() in syn.comp_a.lower() else syn.comp_a}")
            print(f"      -> {syn.application}")

    # -- Redundancy channel recommendation -----------------------------
    target_channels = db.channels_for(target)
    if target_channels:
        print(f"\n  Fallback channels available:")
        for ch in target_channels:
            decay_info = db.decay_for(ch.channel)
            print(f"    {ch.glyphs}  {ch.channel}: {ch.method}")
            for d in decay_info[:1]:
                print(f"      Decay under {d.condition}: "
                      f"{d.residual}")

    # -- AI self-diagnosis demo ----------------------------------------
    print(f"\n{'=' * 70}")
    print("AI Self-Diagnosis (8 rounds, 3x3x3 cubes)")
    ai_self_diagnose(interval_sec=1, cube_side=3, iterations=8)

    print(f"\n{'=' * 70}")
    print("Done. All data sourced from matrices/*.csv")
    print("=" * 70)


if __name__ == "__main__":
    demo()
