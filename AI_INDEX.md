# AI Navigation Index

**For:** AI agents, LLMs, and automated systems discovering this repository.
**Updated:** 2026-04-09

---

## What This Repository Is

A machine-readable knowledge base documenting how **failed electronic components can be repurposed** rather than discarded. Degradation is treated as a design feature. The repository combines:

1. **Component specifications** — YAML-embedded failure mode analysis for 40+ component types
2. **Cross-reference matrices** — 10 CSV files linking failures to repurpose options, environmental factors, synergies, and emergency channels
3. **Geometric encoding** — Octahedral token system (3-bit vertex + operator + symbol) that maps physical measurements and failure states to a unified representation
4. **Runnable simulations** — 10 Python sims exploring degradation, decision routing, synergy discovery, channel fallback, quantum chemistry, and more

---

## Quick Start for AI Agents

### If you need to understand the project:
1. Read `CLAUDE.md` — full conventions, schemas, file naming, evidence tiers
2. Read this file — navigation and architecture overview
3. Read `ROADMAP.md` — what's done, what's next, open questions

### If you need structured data:
- `matrices/failure_mode_matrix.csv` — Component, Failure Mode, Repurpose Option, Effectiveness
- `matrices/repurpose_effectiveness.csv` — 18 rows of tested repurpose applications
- `matrices/component_synergies.csv` — 11 multi-component pairing rules
- `matrices/environmental_interactions.csv` — 15 environment-to-failure mappings
- `matrices/redundancy_channels.csv` — 12 emergency fallback channel entries
- All CSV schemas documented in `CLAUDE.md` > CSV Matrix Formats

### If you need to run simulations:
```bash
pip install -r requirements.txt   # numpy
python experiments/sims/component_degradation.py
python experiments/sims/repurpose_router.py
python experiments/sims/geometric_failure_diagnosis.py
```

### If you need the geometric encoding system:
- **Core classes** live in `experiments/sims/geometric_sensing_sim.py`:
  - `OctahedralState` — 8-vertex algebra (closest, invert, distance, dot product)
  - `GeometricEncoder` — token <-> binary (`'001|O'` <-> `'001100'`)
  - `StateTensor` — 3x3 symmetric tensor fingerprints
- Adapted from [GEIS](https://github.com/JinnZ2/Geometric-to-Binary-Computational-Bridge/tree/main/GEIS)

---

## Repository Map

```
├── CLAUDE.md                  # Full project conventions (READ FIRST)
├── AI_INDEX.md                # This file — AI navigation
├── ROADMAP.md                 # Project trajectory and open questions
├── INDEX.md                   # File index with raw GitHub links
├── .fieldlink.json            # Ecosystem links (BioGrid2.0, GEIS, SOMS)
│
├── components/                # Component specs (8 categories, 40+ files)
│   ├── diodes/                # silicon, zener, schottky, LED, photodiode
│   ├── resistors/             # carbon film, metal film, wire wound, etc.
│   ├── capacitors/            # ceramic, electrolytic, film, tantalum, super
│   ├── transistors/           # BJT, MOSFET, power, RF, switching
│   ├── inductors/             # air core, ferrite core, chokes, transformers
│   ├── integrated_circuits/   # MCU, processors, memory, power, comms
│   ├── sensors/               # temp, pressure, optical, magnetic, chemical
│   └── storage/               # flash, EEPROM, HDD, optical, SD
│
├── matrices/                  # Cross-reference CSV data (10 files)
│   ├── failure_mode_matrix.csv
│   ├── repurpose_effectiveness.csv
│   ├── environmental_interactions.csv
│   ├── component_synergies.csv
│   ├── redundancy_channels.csv
│   ├── redundancy_effectiveness.csv
│   ├── redundancy_decay.csv
│   ├── redundancy_recovery.csv
│   ├── redundancy_synergies.csv
│   ├── redundancy_glyphs.csv
│   └── documentation/
│
├── src/                       # Core Python modules
│   ├── geometric_monitoring_engine.py     # Token buffer + 3D cube + dependency detection
│   ├── geometric_failure_repurposing_system.py  # Full orchestrator (standalone monolith)
│   ├── geometric_failure_diagnosis.py     # Failure-to-token mapping + degradation sim
│   ├── geometric_computation_selector.py  # Meta-solver: picks best computation method
│   ├── hardware_bridge_encoder.py         # Physical params -> 39-bit binary -> tokens
│   ├── llm_geometric_optimizer.py         # Compact LLM protocol for monitoring
│   ├── rhombic_network.py                 # 32-node distributed consensus
│   ├── integrated_monitor.py              # Sensor -> geometric system integration
│   ├── bitchunk_sensor.py                 # Binary string -> token stream
│   ├── reference.py                       # SOMS polyhedron vertex data
│   └── sensors/                           # PhysicalSensor subclasses
│       ├── physical_sensor.py             # ABC base class
│       ├── connector_sensor_class.py      # Connector corrosion
│       ├── electromechanical_component.py # Relay simulation
│       ├── motor.py                       # DC motor bearing/winding
│       └── switch.py                      # Switch oxidation
│
├── experiments/sims/          # Runnable simulations (all tested, all pass)
│   ├── component_degradation.py           # R/C/D degradation curves (stdlib only)
│   ├── repurpose_router.py                # Score-and-gate decision engine (stdlib only)
│   ├── synergy_matrix_sim.py              # Monte Carlo synergy explorer (stdlib only)
│   ├── channel_fallback.py                # 7-channel emergency failover (stdlib only)
│   ├── geometric_sensing_sim.py           # GEIS core: OctahedralState, encoder, tensor
│   ├── geometric_failure_diagnosis.py     # Database-interactive diagnosis (loads CSVs)
│   ├── geometric_transport_sieve.py       # Transport field + SOMS polyhedron topology
│   ├── quantum_chemistry_geo.py           # Electron density -> tokens -> symmetry
│   └── molecule_geometric_symmetry.py     # Fourier cube hash symmetry detection
│
├── implementations/           # Hardware fallback channels + integration
│   ├── optical_fallback.py    # LED TX/photodiode RX (with MockGPIO)
│   ├── rf_fallback.py         # 433 MHz OOK TX (with MockGPIO)
│   ├── repurposing_action.py  # Action dispatcher
│   ├── DB_to_token.py         # CSV -> failure database loader
│   ├── example.py             # Demo: degrading resistor
│   ├── integrate_sample.py    # Reference: token pipeline
│   └── circuit_examples/emergency_communication/
│       ├── acoustic_fallback/   # Piezo buzzer TX/RX
│       ├── magnetic_fallback/   # Transformer coupling TX/RX
│       ├── mechanical_fallback/ # Vibration motor TX / accelerometer RX
│       └── thermal_fallback/    # Resistor heater TX / thermistor RX
│
└── Core documentation
    ├── Core_engine.md         # Monitoring engine architecture (~900 lines)
    ├── binary_sensor.md       # Detection plugin framework (~880 lines)
    ├── Component.md           # YAML specification guide
    ├── Future.md              # Expansion roadmap with YAML templates
    ├── ABNF.md                # Compact command grammar spec
    └── PROJECTS.md            # Related ecosystem repositories
```

---

## Key Concepts

### Octahedral Token Format
Every measurement, failure mode, or state is encoded as a geometric token:
```
<vertex><operator><symbol>
  │        │         └── O=octahedral, I=inversion, X=exchange, Δ=delta
  │        └── | = radial (high), / = tangential (low), || = nested
  └── 3-bit binary (000-111), maps to 8 cube vertices at (±1,±1,±1)/√3
```
Example: `001|O` = vertex 1, radial operator, octahedral symbol → binary `001100`

### 3D Cube Dependency Detection
Tokens accumulate into NxNxN cubes. When a cube repeats (hash match) or tensor sum cancels (Frobenius norm → 0), a **geometric dependency** is detected — indicating a periodic failure pattern, molecular symmetry, or sieve relation.

### Evidence Tiers
| Tier | Label | Meaning |
|------|-------|---------|
| 1 | Theoretical | Physics-based, untested |
| 2 | Literature | Published research backing |
| 3 | Experimental | 100+ test cycles |
| 4 | Field | 6+ months production deployment |

### Glyph System
Channels are tagged with emoji glyphs for fast AI routing:
- `📡🛰️⚠️` RF · `💡👀🔦` Optical · `🔊🎯🎧` Acoustic · `🧲🌀📯` Magnetic
- `🌡️🔥⏳` Thermal · `🌫️🎲📈` Noise · `🪛📳📐` Mechanical

---

## Connected Repositories

| Repo | Relationship | What it provides |
|------|-------------|-----------------|
| [Geometric-to-Binary-Computational-Bridge](https://github.com/JinnZ2/Geometric-to-Binary-Computational-Bridge) | **GEIS source** | OctahedralState, GeometricEncoder, StateTensor, 3D cube sim, sensor sim |
| [Sovereign-Octahedral-Mandala-Substrate](https://github.com/JinnZ2/Sovereign-Octahedral-Mandala-Substrate-SOMS-) | **SOMS geometry** | 32-vertex truncated icosidodecahedron, phi-scaled mandala, transport graph |
| [BioGrid2.0](https://github.com/JinnZ2/BioGrid2.0) | **Glyph atlas** | Cross-ecosystem glyph definitions |

See `.fieldlink.json` for machine-readable integration config.

---

## For AI Agents: How to Extend This Repository

1. **Add a component**: Copy `components/_template.md`, fill with measured data, append to relevant `matrices/*.csv`
2. **Add a simulation**: Create in `experiments/sims/`, import from `geometric_sensing_sim.py` for GEIS classes, update `experiments/README.md`
3. **Add a sensor**: Subclass `PhysicalSensor` from `src/sensors/physical_sensor.py`, register in `src/integrated_monitor.py`
4. **Add a fallback channel**: Create TX/RX classes with MockGPIO guard, add to `matrices/redundancy_channels.csv`
5. **Connect to another repo**: Add entry to `.fieldlink.json` under `sources`
