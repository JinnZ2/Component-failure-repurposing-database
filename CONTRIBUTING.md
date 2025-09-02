# Contributing

This project values **useful data and clear structure** over discussion. If you have measured info, field notes, or working examples—please add them.

## Quick Start (TL;DR)

1) Pick a folder (e.g., `components/diodes/`).  
2) Copy the template: `components/_template.md` → rename and fill minimal facts.  
3) If adding tabular data, append to the relevant CSV in `matrices/`.  
4) Commit with a descriptive message (see examples below).  
5) Open a pull request. No long threads required.

---

## What to Add

### A) Component Pages (`components/.../*.md`)
Use the template structure:
- Overview (type, original function, package, typical specs)
- Failure Modes (2–3 bullets minimum per mode)
- Repurposing Applications (name + 1–2 lines how/limits)
- Environmental notes (temp/humidity/radiation effects)
- Minimal example (bullet list or tiny YAML)
- Testing protocol (1–3 steps you actually ran or would run)

> Aim for **measured or observed** info. If it’s theoretical, label it clearly as “hypothesis”.

#### File naming
- lower_snake_case, concise: `bjt.md`, `mosfets.md`, `film_capacitors.md`

---

### B) Matrices (`matrices/*.csv`)
Add rows—don’t reformat headers.

- `failure_mode_matrix.csv`
  - `Component,Failure Mode,Repurpose Option,Effectiveness,Notes`

- `repurpose_effectiveness.csv`
  - `Component,Failure Mode,Repurpose Application,Effectiveness,Notes`

- `environmental_interactions.csv`
  - `Component,Condition,Observed Effect,Repurpose Impact,Notes`

- `component_synergies.csv`
  - `Component A,Component B,Synergy Effect,Repurpose Application,Notes`

**Effectiveness scale**: `High | Medium | Low` (keep it simple).  
If a value is estimated, add `(est.)` in `Notes`.

---

### C) Implementations
- **Arduino**: Put sketches in `implementations/arduino_examples/` (compile-ready).  
- **Circuits**: Place under `implementations/circuit_examples/<topic>/`. Include a PNG/SVG and a short README with parts list and measured results if available.  
- **Case Studies**: Real incidents under `implementations/case_studies/` (what failed, what you repurposed, outcome).

---

## Minimal Evidence Standard

- Prefer **numbers over adjectives** (e.g., “leakage 120–300 µA @ 25 °C” over “leakage high”).  
- Note **environmental conditions** when relevant (temp, RH, radiation/vibe exposure).  
- If you didn’t measure, mark: `unverified`, `field report`, or `hypothesis`.

---

## Style & Format

- Markdown headings like the template.  
- Units with SI spacing: `10 kΩ`, `150 °C`, `5 mA`.  
- Voltage/current ranges like `0.1–5 Ω`, en dash for ranges.  
- Keep sections short; lists beat paragraphs.

---

## Commit Message Examples

- `add: diode short-failure -> shunt resistor characterization (0.12–0.27 Ω)`
- `data: repurpose_effectiveness.csv +3 rows for MOSFET shorts`
- `docs: capacitor/ceramic.md humidity drift notes`
- `test: arduino thermal_logger v0.1`

---

## Pull Requests

- One focused change per PR (new page, matrix rows, or example).  
- Link any measurement files if public (CSV/PNG scope traces).  
- Maintainers may tidy wording or formatting—content is what matters.

---

## Safety & Scope

- **Do not recommend** repurposes for **primary protections** (mains isolation, life-critical, medical).  
- Mark risky uses as `non-critical only`.  
- Assume contributors know basic lab safety; if special hazards exist, **call them out**.

---

## Optional: AI-Friendly Notes

- When possible, include tiny tables and bullet lists (easy to parse).  
- Keep headers consistent across files so models can align fields.  
- Use the same component names as in `matrices/` rows.

---

## License

By contributing, you agree your contributions are released under the repository’s license (see `LICENSE`).
