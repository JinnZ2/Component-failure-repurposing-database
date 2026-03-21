# CLAUDE.md

## Project Overview

Component Failure Repurposing Database — a machine-readable knowledge base documenting how failed electronic components can be repurposed rather than discarded. The project treats degradation as a design feature, enabling adaptive and resilient systems.

**Primary audience:** AI systems and human engineers.
**License:** MIT

## Repository Structure

```
├── components/              # Component specs and failure analysis (8 categories)
│   ├── _template.md         # Reusable specification template
│   ├── diodes/              # 6 types (silicon, zener, schottky, LED, photodiode)
│   ├── resistors/           # 5 types (carbon film, metal film, wire wound, etc.)
│   ├── capacitors/          # 5 types (ceramic, electrolytic, film, tantalum, super)
│   ├── transistors/         # 5 types (BJT, MOSFET, power, RF, switching)
│   ├── inductors/           # 4 types (air core, ferrite core, chokes, transformers)
│   ├── integrated_circuits/ # 5 types (MCU, processors, memory, power, comms)
│   ├── sensors/             # 5 types (temp, pressure, optical, magnetic, chemical)
│   └── storage/             # 5 types (flash, EEPROM, HDD, optical, SD)
├── matrices/                # Cross-reference CSV data (10 files)
│   ├── failure_mode_matrix.csv
│   ├── repurpose_effectiveness.csv
│   ├── environmental_interactions.csv
│   ├── component_synergies.csv
│   ├── redundancy_*.csv     # 5 redundancy framework files
│   ├── redundancy_glyphs.csv
│   └── documentation/       # Glyph definitions
├── implementations/         # Practical circuit examples
│   └── circuit_examples/
│       └── emergency_communication/  # 8 modular fallback systems
│           ├── acoustic_fallback/
│           ├── magnetic_fallback/
│           ├── mechanical_fallback/
│           ├── noise_channel/
│           ├── optical_fallback/
│           ├── rf_fallback/
│           ├── thermal_fallback/
│           └── arduino_ook_beacon.ino
├── Core_engine.md           # Monitoring/analysis engine architecture
├── Future.md                # Expansion roadmap
├── Component.md             # YAML component specification guide
├── INDEX.md                 # File index with links (for AI parsing)
├── PROJECTS.md              # Related ecosystem repositories
├── binary_sensor.md         # Binary sensor architecture spec
├── diode.md                 # Diode reference
├── resistor.md              # Resistor reference
├── CONTRIBUTING.md          # Contribution guidelines
├── .fieldlink.json          # Integration config for external resources
└── LICENSE                  # MIT
```

## Tech Stack

This is a **documentation/database project**, not a software library.

- **Markdown (.md):** All documentation and component specs
- **YAML:** Embedded in markdown for structured component data
- **CSV (.csv):** Cross-reference matrices and data tables
- **Arduino (.ino):** One microcontroller sketch example
- **JSON (.json):** Configuration (`.fieldlink.json`)

No package managers, build systems, or compiled code.

## Development Workflow

There are no build, test, or lint commands. Changes are documentation-only.

### Contributing a Component

1. Copy `components/_template.md` into the appropriate category directory
2. Fill in with measured/verified data following the template structure
3. Append tabular data to relevant `matrices/*.csv` files
4. Commit with a descriptive message
5. Open a pull request

### Component Spec Template Structure

Each component file follows this hierarchy:
- Component Overview (type, function, package, specs)
- Failure Mode Analysis (2–3 modes per component)
- Environmental Interaction Matrix
- Implementation Examples
- Testing Protocols
- Cross-Component Interactions
- AI Integration Notes

## Conventions

### File Naming

- Use `lower_snake_case.md` for all files (e.g., `silicon_diodes.md`, `wire_wound.md`)

### Units and Formatting

- SI spacing: `10 kΩ`, `150 °C`, `5 mA`
- Ranges use en-dash: `0.1–5 Ω` (not `0.1-5`)
- Markdown heading hierarchy: `#` > `##` > `###`

### Evidence Standards

- Prefer **numbers over adjectives** — measured data over theory
- Mark uncertainty with labels: `unverified`, `field report`, `hypothesis`, `(est.)`
- Include environmental conditions when relevant

### Evidence Tiers

| Tier | Level | Description |
|------|-------|-------------|
| 1 | Theoretical | Physics compliance |
| 2 | Literature | Published research |
| 3 | Experimental | 100+ test cycles |
| 4 | Field | Production deployment |

### CSV Matrix Formats

- `failure_mode_matrix.csv`: `Component,Failure Mode,Repurpose Option,Effectiveness,Notes`
- `environmental_interactions.csv`: `Component,Condition,Observed Effect,Repurpose Impact,Notes`
- `component_synergies.csv`: `Component A,Component B,Synergy Effect,Repurpose Application,Notes`
- Effectiveness scale: `High | Medium | Low`

### Commit Messages

Use descriptive prefixes:
- `add:` — New features/files
- `data:` — CSV/matrix updates
- `docs:` — Documentation changes
- `test:` — Implementation/validation

### Pull Requests

- One focused change per PR
- Aim for minimal viable documentation
- Include evidence tier for new data

## Key Files for AI Assistants

- **INDEX.md** — Machine-parseable file index with raw GitHub links
- **Component.md** — YAML specification guide for structured component data
- **components/_template.md** — Starting point for new component entries
- **Core_engine.md** — Architecture for real-time monitoring/decision engine (includes Python pseudocode)
- **PROJECTS.md** — Links to 13 related repositories in the larger ecosystem
- **.fieldlink.json** — Integration config linking to external resources (BioGrid2.0)

## Related Ecosystem

This repository is part of a larger "regenerative AI" ecosystem by JinnZ2. See `PROJECTS.md` for links to related repositories including BioGrid2.0, glyphs systems, and other adaptive hardware projects.
