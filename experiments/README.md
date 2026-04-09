# Experiments — Sample Simulations

**Purpose:** Runnable simulations that explore interfaces and possibilities for component failure repurposing. Each sim models a different aspect of the database's core concepts — degradation curves, repurpose decision-making, multi-component synergies, and emergency channel fallback.

**Dependencies:** Python 3.8+ standard library only for most sims. The geometric sims require **numpy**.

-----

## Simulations

| File | What it explores |
|------|-----------------|
| `sims/component_degradation.py` | Time-series degradation of resistors, capacitors, and diodes — models drift, ESR rise, and leakage over operational hours with configurable stress profiles |
| `sims/repurpose_router.py` | Decision interface that takes a degraded component's health snapshot and routes it to the best repurposing application using a scored rule engine |
| `sims/synergy_matrix_sim.py` | Monte Carlo exploration of multi-component failure combinations — discovers emergent synergies by randomly pairing degraded components and scoring outcomes |
| `sims/channel_fallback.py` | Emergency communication channel switching — simulates degradation across RF, optical, acoustic, thermal, and mechanical channels with automatic failover |
| `sims/geometric_sensing_sim.py` | Real-time 3D geometric sensing — reads accelerometer data (Termux or simulated), encodes to octahedral tokens via GEIS, fills 3D cubes, detects dependencies via cube matching and tensor cancellation |
| `sims/geometric_failure_diagnosis.py` | Maps database failure modes to octahedral tokens, simulates component degradation driven by `matrices/*.csv`, detects periodic failure signatures via cube cancellation, includes AI self-diagnosis loop |
| `sims/geometric_transport_sieve.py` | Self-organising probability field over offset space for number-theoretic relation collection — compares ring vs SOMS 32-vertex polyhedron topology, encodes sieve state as geometric tokens |
| `sims/quantum_chemistry_geo.py` | Maps molecular electron density to octahedral tokens — Slater-type atomic orbitals on a 3D grid, density gradient -> vertex, magnitude -> operator, orbital character -> symbol. Detects molecular symmetry via cube rotation invariance, finds bonding interactions via tensor cancellation, simulates H2 dissociation curve |
| `sims/molecule_geometric_symmetry.py` | Fourier cube hash approach to molecular symmetry — builds 8x8x8/10x10x10 state cubes from electron density, detects rotational symmetry via rotation-invariant FFT hashing. Demos: H2 and CH4 |
| `sims/end_to_end_test.py` | Integration test: sensor -> HardwareBridgeEncoder -> TokenBuffer -> cube dependency -> FailureDatabase -> RepurposeOrchestrator. Exercises Environment, EnvironmentalMemory, feed_geometry(), AI self-diagnosis |

-----

## Running

Each simulation is self-contained and runs from the repo root:

```bash
python experiments/sims/component_degradation.py
python experiments/sims/repurpose_router.py
python experiments/sims/synergy_matrix_sim.py
python experiments/sims/channel_fallback.py
python experiments/sims/geometric_sensing_sim.py           # requires numpy
python experiments/sims/geometric_failure_diagnosis.py     # requires numpy
python experiments/sims/geometric_transport_sieve.py       # requires numpy
python experiments/sims/quantum_chemistry_geo.py           # requires numpy
python experiments/sims/molecule_geometric_symmetry.py     # requires numpy
python experiments/sims/end_to_end_test.py                 # requires numpy
```

All sims print results to stdout. Pipe to a file for post-analysis:

```bash
python experiments/sims/component_degradation.py > results/degradation_run.txt
```

-----

## Structure

```
experiments/
├── README.md              # This file
└── sims/
    ├── __init__.py
    ├── component_degradation.py
    ├── repurpose_router.py
    ├── synergy_matrix_sim.py
    ├── channel_fallback.py
    ├── geometric_sensing_sim.py
    ├── geometric_failure_diagnosis.py
    ├── geometric_transport_sieve.py
    ├── quantum_chemistry_geo.py
    ├── molecule_geometric_symmetry.py
    └── end_to_end_test.py
```

-----

## Extending

1. Copy an existing sim as a starting point
2. Follow the interface pattern: each sim defines a `run()` function and a `if __name__ == "__main__"` block
3. Keep to stdlib — simulations should be zero-install
4. Document assumptions and parameter ranges inline
5. Tag outputs with evidence tier labels where applicable (`Theoretical`, `Literature`, `Experimental`)

-----

## Relationship to Core Architecture

These sims prototype interfaces described in:

- **`Core_engine.md`** — Data acquisition and plugin dispatch patterns
- **`binary_sensor.md`** — Health scoring and failure mode detection
- **`Future.md`** — Expanded component templates and validation tiers
- **`matrices/component_synergies.csv`** — Cross-component pairing data used by `synergy_matrix_sim.py`

## External Dependencies

`geometric_sensing_sim.py` integrates components from the
[GEIS](https://github.com/JinnZ2/Geometric-to-Binary-Computational-Bridge/tree/main/GEIS)
(Geometric Information Encoding System) library:

| GEIS Module | What was pulled in |
|-------------|-------------------|
| `octahedral_state.py` | `OctahedralState` class — vertex algebra, inversion, distance, token/binary conversion |
| `geometric_encoder.py` | `GeometricEncoder` class — bidirectional token-to-binary encoding with operators and symbols |
| `state_tensor.py` | `StateTensor` class — 3x3 symmetric tensor fingerprints, projection, eigenvalues |
| `geometric_sensor_sim.py` | `find_dependencies()` — tensor cancellation search (pairs, triples, meet-in-the-middle) |
| `3D_cube_sim.py` | Cube XOR dependency detection, canonical form concepts |

`geometric_failure_diagnosis.py` reads live data from `matrices/*.csv` (failure modes,
repurpose effectiveness, environmental interactions, synergies, redundancy channels, decay).

`geometric_transport_sieve.py` integrates the 32-vertex truncated icosidodecahedron from the
[SOMS](https://github.com/JinnZ2/Sovereign-Octahedral-Mandala-Substrate-SOMS-)
(Sovereign Octahedral Mandala Substrate) repository as a transport graph topology.
