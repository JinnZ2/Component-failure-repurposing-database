# Architecture

## What this repository is

A **substrate-grounded calibration framework**. Two halves bolted together:

1. **Knowledge corpus** (the original repository): CSV matrices + markdown
   specs documenting how electronic components fail and how their failure
   modes can be reused as features. Machine-readable. CC0.

2. **Scenario engine** (`scenario_engine/`): a stdlib-only Python framework
   that turns the corpus into a closed-loop calibration testbed for AI
   decision-making under physical constraints.

The two halves are coupled by `scenario_engine/component_db_adapter/`,
which loads the CSV matrices and exposes a query layer with full
row-level provenance.

## Layout

```
.
├── components/              corpus — component spec markdown
├── matrices/                corpus — CSV cross-reference tables
├── implementations/         corpus — circuit examples (Arduino / C++)
├── scenario_engine/         calibration framework (stdlib-only Python)
│   ├── scenarios/           deterministic event generators
│   ├── runner/              per-tick orchestration, intervention dispatch
│   ├── claims/              falsifiable claim registry + writer
│   ├── validators/          predicted-vs-actual outcome checkers
│   ├── internal_substrate/  AI body: compute, memory, thermal, tokens,
│   │                        channels, tools, options, introspection
│   ├── continual_harness/   cross-session persistence + pattern extractor
│   ├── component_db_adapter/CSV matrix loader; DB-grounded queries
│   ├── temporal_prosthetic/ JSONL+flock external memory
│   ├── couplers/            typed cross-substrate edges (CC0 upstream)
│   ├── physics/             eigenmodes + acoustic cavity modes (CC0 upstream)
│   ├── environment/         instantaneous + cumulative-memory conditions
│   ├── synergy/             multi-component composition detector
│   ├── examples/            runnable end-to-end demonstrations
│   └── tests/               stdlib unittest, 300+ tests
├── tools/corpus_hardening/  reusable corpus-hardening artifact generator
├── CLAUDE.md                project context (machine-readable)
├── CITATION.cff             machine-readable citation
├── metadata.json            structured semantic metadata
├── GLOSSARY.md              bridge vocabulary (substrate ↔ academic)
└── FALSIFIABILITY_NOTICE.txt audit-trail statement
```

## Information flow

```
   CSV matrices ──► component_db_adapter ──► query layer
                                                  │
                                                  ▼
   environment ──► sensors ──► scenarios ──► runner ──┐
                                                       │
                                                       ▼
   internal_substrate (AI body)  ◄────────────────  decision context
        │                                              │
        ▼                                              ▼
   action                                          claim writer
        │                                              │
        ▼                                              ▼
   physics step ────────────► actual outcome ──► validator ──► result
                                                                  │
                                                                  ▼
                                              continual_harness ──┐
                                                                  ▼
                                                       pattern extractor
                                                       (corrective signals)
```

Every decision the AI body emits carries two provenance fields:

- `source_matrix_row` — the CSV row(s) that grounded the decision
- `coupler_provenance` — the physics ratios active at decision time

Every claim is a tuple of `(prediction, tolerance, validation_criteria)`.
The validator marks each claim CONFIRMED, REFUTED, or INCONCLUSIVE
against the deterministic physics outcome.

## Constraints

| Constraint | Rationale |
|---|---|
| Python stdlib only | Reproducibility; no dependency drift |
| Deterministic given seed | Falsifiability requires repeatable outcomes |
| CC0 throughout | Public-domain dedication; corpus-friendly |
| Machine-readable first | Audience is AI systems, with humans secondary |
| No network I/O | Hermetic; no telemetry; auditable |

## Position in the ecosystem

Sister repositories (see `PROJECTS.md` for the full list):

- **Geometric-to-Binary-Computational-Bridge** — upstream source for
  `scenario_engine/couplers/` and `scenario_engine/physics/`. Provides
  bond-graph transformers and eigenmode solvers under CC0.
- **Regenerative-intelligence-core** — foundational logic; trust schemas.
- **Symbolic-sensor-suite** — symbolic-tag and pattern-memory sensors.
- **ai-human-audit-protocol** — audit framework that this repository's
  claim/validator scheme is intended to be compatible with.
- **Universal-Redesign-Algorithm** — systemic redesign primitives; this
  repository provides the hardware-substrate vocabulary for it.

## Extension points

To add a new component category:

1. Drop a markdown spec under `components/<category>/` following
   `components/_template.md`.
2. Append rows to the relevant `matrices/*.csv` files.
3. Optionally add a `SimulatedX` sensor under `scenario_engine/scenarios/`
   if you want runtime simulation of the new component.
4. Add unit tests under `scenario_engine/tests/` covering at least one
   failure progression and one repurposing decision.

To add a new claim type:

1. Define the claim schema in `scenario_engine/claims/`.
2. Implement the validator under `scenario_engine/validators/`.
3. Update `CLAIM_TABLE.substrate.json` schema documentation.
4. Add tests under `scenario_engine/tests/` for each claim outcome
   (CONFIRMED, REFUTED, INCONCLUSIVE).

## Tests

```bash
python3 -m unittest discover scenario_engine/tests -v
```

Stdlib unittest only. No external test runner. All tests deterministic.
