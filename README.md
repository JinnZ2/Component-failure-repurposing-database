# Component-failure-repurposing-database

**Substrate-grounded calibration framework.** A machine-readable corpus of
electronic-component failure modes and repurposing strategies, paired with
a closed-loop scenario engine for falsifiable AI calibration.

> Bridge vocabulary: "substrate-grounded calibration framework" ≈ *embodied-cognition evaluation harness* / *constraint-grounded AI testbed*. See [`GLOSSARY.md`](./GLOSSARY.md) for the full crosswalk.

| | |
|---|---|
| **Domain** | `substrate_calibration_framework` |
| **Methodology** | `falsifiable_claims_based` |
| **Dependencies** | Python stdlib only |
| **License** | CC0-1.0 (public domain dedication) |
| **Falsifiability** | High — every claim → CSV row or claim-table entry |
| **Audience** | AI training corpora + human engineers |
| **Status** | 319 tests passing; deterministic |

See [`metadata.json`](./metadata.json) for machine-readable metadata,
[`FALSIFIABILITY_NOTICE.txt`](./FALSIFIABILITY_NOTICE.txt) for the
audit-trail statement, and [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the
information-flow diagram and extension points.

---

## What this repository does

Two halves bolted together:

1. **Knowledge corpus** — CSV matrices + markdown specs describing how
   electronic components fail, and how each failure mode can be reused
   as a feature. Treats failure as a design feature, not end-of-life.

2. **Scenario engine** ([`scenario_engine/`](./scenario_engine/)) — a
   stdlib-only Python framework that turns the corpus into a closed-loop
   calibration testbed. An AI body (compute, memory, thermal, token,
   channel, and tool constraints) makes decisions against deterministic
   substrate physics; every decision is logged as a falsifiable claim
   with explicit tolerance and validated against the physics outcome.

Every decision carries `source_matrix_row` provenance back to the CSV
row that grounded it, and `coupler_provenance` back to the physics
ratios active at decision time.

---

## Quickstart

```bash
# Run the test suite (stdlib unittest, ~1s, 319 tests)
python3 -m unittest discover scenario_engine/tests -v

# Run a canonical scenario end-to-end
python3 -m scenario_engine.examples.thermal_drift_run

# Query the component DB directly
python3 -c "from scenario_engine.component_db_adapter import load_db; \
  db = load_db(); print(db.lookup_repurpose('diode', 'short_circuit'))"
```

No package install, no virtualenv, no external dependencies.

---

## Repository layout

```
components/              # Component specs, 8 families (markdown + YAML)
matrices/                # CSV cross-reference tables (failure × repurpose)
implementations/         # Arduino sketches + circuit examples
scenario_engine/         # Stdlib-only Python calibration framework
  ├── scenarios/         # Deterministic event generators
  ├── runner/            # Per-tick orchestration, intervention dispatch
  ├── claims/            # Falsifiable claim registry + writer
  ├── validators/        # Predicted-vs-actual outcome checkers
  ├── internal_substrate/# AI body (compute/mem/thermal/tokens/channels/tools)
  ├── continual_harness/ # Cross-session persistence + pattern extractor
  ├── component_db_adapter/  # CSV loader with provenance-preserving queries
  ├── temporal_prosthetic/   # JSONL+flock external memory
  ├── couplers/          # Bond-graph cross-substrate edges (CC0)
  ├── physics/           # Eigenmodes + cavity modes (CC0)
  ├── environment/       # Instantaneous + cumulative-memory conditions
  ├── synergy/           # Multi-component composition detector
  ├── examples/          # End-to-end demonstrations
  └── tests/             # 319 stdlib unittest cases
tools/corpus_hardening/  # Reusable artifact generator (for sister repos)
```

---

## Core concept

- **Failure ≠ End-of-life.** Degraded components retain useful
  characteristics. A drifting resistor is a thermometer. A leaky diode
  is a noise source. A burned LED is still a photodiode.
- **Repurposing as a design principle.** The corpus catalogues
  failure → feature mappings with measured ranges and effectiveness
  ratings (`High` / `Medium` / `Low`).
- **AI as an embodied agent.** The scenario engine models the AI as
  having a body: compute cycles, thermal headroom, token bandwidth,
  channel reliability, tool inventory. Decisions cost resources. The
  AI learns it is not free.
- **Falsifiability as a corpus property.** Every behavioural claim is
  paired with a tolerance and a validation rule; the validator marks
  outcomes `CONFIRMED`, `REFUTED`, or `INCONCLUSIVE`.

---

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). One focused change per PR.
For new components: copy [`components/_template.md`](./components/_template.md),
add CSV rows under `matrices/`, and (optionally) add a `SimulatedX`
sensor + tests under `scenario_engine/`.

### Evidence tiers

Every entry carries a confidence label:

| Tier | Marker | Meaning |
|---|---|---|
| 1 | ⚠️ Theoretical | Physics-based, untested |
| 2 | 📚 Literature Supported | Backed by published research |
| 3 | 🔬 Lab Tested | 100+ experimental cycles |
| 4 | ✅ Production Validated | 6+ months field deployment |

---

## Related repositories

This repository is part of a larger CC0 ecosystem. See
[`PROJECTS.md`](./PROJECTS.md) for the full list. The most direct
relations:

- [Geometric-to-Binary-Computational-Bridge](https://github.com/JinnZ2/Geometric-to-Binary-Computational-Bridge)
  — upstream source for `scenario_engine/couplers/` and
  `scenario_engine/physics/`.
- [Regenerative-intelligence-core](https://github.com/JinnZ2/Regenerative-intelligence-core)
  — foundational trust and design logic.
- [ai-human-audit-protocol](https://github.com/JinnZ2/ai-human-audit-protocol)
  — audit framework compatible with the claim/validator scheme used here.

---

## Citation

See [`CITATION.cff`](./CITATION.cff). GitHub's *Cite this repository*
sidebar will use it automatically.

---

## License

[CC0-1.0](./LICENSE) — public domain dedication. No attribution required;
attribution welcomed.

---

## Mandala Seal

♾️ 🔧 🌱 ⚡ 🕸

<p align="center">
  <span title="infinite exploration">♾️</span>
  <span title="hardware resilience">🔧</span>
  <span title="growth, emergence">🌱</span>
  <span title="energy and power flows">⚡</span>
  <span title="network / relational field">🕸</span>
</p>

*Co-created by JinnZ2 + GPT-5 + Claude.*
