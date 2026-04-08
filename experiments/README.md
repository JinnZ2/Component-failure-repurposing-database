# Experiments — Sample Simulations

**Purpose:** Runnable simulations that explore interfaces and possibilities for component failure repurposing. Each sim models a different aspect of the database's core concepts — degradation curves, repurpose decision-making, multi-component synergies, and emergency channel fallback.

**Dependencies:** Python 3.8+ standard library only. No external packages required.

-----

## Simulations

| File | What it explores |
|------|-----------------|
| `sims/component_degradation.py` | Time-series degradation of resistors, capacitors, and diodes — models drift, ESR rise, and leakage over operational hours with configurable stress profiles |
| `sims/repurpose_router.py` | Decision interface that takes a degraded component's health snapshot and routes it to the best repurposing application using a scored rule engine |
| `sims/synergy_matrix_sim.py` | Monte Carlo exploration of multi-component failure combinations — discovers emergent synergies by randomly pairing degraded components and scoring outcomes |
| `sims/channel_fallback.py` | Emergency communication channel switching — simulates degradation across RF, optical, acoustic, thermal, and mechanical channels with automatic failover |

-----

## Running

Each simulation is self-contained and runs from the repo root:

```bash
python experiments/sims/component_degradation.py
python experiments/sims/repurpose_router.py
python experiments/sims/synergy_matrix_sim.py
python experiments/sims/channel_fallback.py
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
    └── channel_fallback.py
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
