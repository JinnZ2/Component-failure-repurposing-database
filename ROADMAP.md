# Roadmap

**Project:** Component Failure Repurposing Database
**Updated:** 2026-04-09

---

## Completed

### Phase 1 — Knowledge Base (v1.0)
- [x] 40+ component specs across 8 categories (diodes, resistors, capacitors, transistors, inductors, ICs, sensors, storage)
- [x] 10 cross-reference CSV matrices (failure modes, repurpose effectiveness, environmental interactions, synergies, redundancy channels/decay/recovery/synergies/glyphs)
- [x] YAML-embedded structured data in every component file
- [x] Evidence tier system (Theoretical → Literature → Experimental → Field)
- [x] Glyph tagging system for 7 emergency communication channels
- [x] Emergency communication implementations (RF, optical, acoustic, magnetic, thermal, noise, mechanical) with TX/RX designs

### Phase 2 — Geometric Encoding Integration
- [x] OctahedralState, GeometricEncoder, StateTensor adapted from GEIS
- [x] HardwareBridgeEncoder: physical params → 39-bit binary → octahedral tokens
- [x] GeometricMonitoringSystem: token buffer → 3D cube → dependency detection
- [x] FailureDatabase + RepurposeOrchestrator
- [x] LLM compact protocol (ABNF grammar + NL-to-compact translator)
- [x] PhysicalSensor ABC + 5 sensor simulators (connector, relay, motor, switch, resistor)
- [x] Rhombic triacontahedron network (32-node distributed consensus)
- [x] GenericHardwareInterface with environment-aware acceleration factors

### Phase 3 — Experiments & Simulations
- [x] 10 runnable simulations in experiments/sims/ (all tested, all pass)
  - Component degradation (R/C/D time-series)
  - Repurpose decision router (scored rule engine)
  - Synergy matrix explorer (Monte Carlo)
  - Channel fallback orchestrator (7-channel failover)
  - Geometric sensing (accelerometer → tokens → cubes)
  - Geometric failure diagnosis (database-interactive, loads CSVs)
  - Transport sieve (SOMS 32-vertex polyhedron topology)
  - Quantum chemistry (electron density → tokens → symmetry)
  - Molecule geometric symmetry (Fourier cube hash)

### Phase 4 — Ecosystem & Navigation
- [x] .fieldlink.json connecting BioGrid2.0, GEIS, and SOMS repos
- [x] AI_INDEX.md — machine-readable entry point for AI agents
- [x] ROADMAP.md — this file
- [x] Repository restructuring: src/ for Python modules, clean root
- [x] Full audit: import fixes, MockGPIO guards, CSV formatting, duplicate cleanup

---

## In Progress

### GeometricMonitoringSystem Integration (from CLAUDE.md TODO)
- [x] Wire `GeometricMonitoringSystem.feed_geometry()` to accept geometry dicts from `GenericHardwareInterface`
- [x] `HardwareBridgeEncoder.to_octahedral_tokens()` feeding `TokenBuffer`
- [x] Cube dependency callback → `RepurposeOrchestrator` → fallback channel dispatch
- [x] Environment class with `EnvironmentalMemory` (cumulative thermal cycles, humidity exposure, vibration dose)
- [x] End-to-end test: sensor → encoder → buffer → cube → dependency → repurpose action

### Compact Protocol Refinement
- [ ] Resolve component ID ambiguity (e.g., `R1|O 85` — separator between ID and token)
- [ ] Add timestamps to compact health queries (`R1@12.3 85`)
- [ ] Numeric action codes for ultra-low-token scenarios
- [ ] Error recovery grammar (`ERR <code>` responses)

---

## Next

### Phase 5 — Extended Components
- [ ] Connectors/interconnects — contact resistance, insertion cycles, mating force
- [ ] Electromechanical — motor windings, relay contacts, solenoid coils (YAML templates in Future.md)
- [ ] Power components — thermal derating, efficiency curves, protection circuits
- [ ] Connectors — corrosion progression, gold/tin contact degradation

### Phase 6 — Real-World Validation
- [ ] Lab testing: run 100+ failure/repurpose cycles on actual components
- [ ] Calibrate degradation models against measured data
- [ ] Promote entries from Tier 1 (Theoretical) to Tier 3 (Experimental)
- [ ] Raspberry Pi hardware integration test (all fallback channels)
- [ ] Field deployment of emergency communication stack

### Phase 7 — Quantum Chemistry Bridge
- [ ] Interface with PySCF/Psi4 for real density matrices (replace Slater-type approximation)
- [ ] Reaction monitoring: move atoms, watch cube hash change, trigger repurpose
- [ ] Electron flow transport on rhombic triacontahedron graph
- [ ] Map molecular bond breaking → component degradation (cross-domain transfer learning)

### Phase 8 — AI Integration
- [ ] Fine-tune small model (Llama 3 8B) on compact grammar for guaranteed protocol compliance
- [ ] Autonomous repurpose agent: monitors → detects → decides → acts without human intervention
- [ ] Cross-repo AI agent that navigates fieldlink graph between BioGrid2.0, GEIS, SOMS, and this database
- [ ] Predictive maintenance: use geometric dependencies to forecast failures before they happen

---

## Open Questions

1. **Token ambiguity**: How should component IDs be separated from token vertex bits? Current approach uses hashing — is a delimiter-based scheme (`R:1|O`) better for LLM compliance?

2. **Cube size vs resolution**: 4x4x4 cubes (64 tokens) balance speed and sensitivity. Would 8x8x8 (512 tokens) catch more subtle patterns at the cost of latency?

3. **Cross-domain transfer**: Can the same geometric dependency (e.g., C2 symmetry in water) meaningfully map to periodic failure cycles in resistors? Early evidence says yes — needs experimental validation.

4. **Distributed consensus**: The rhombic network `_build()` method is a stub. Should the 32-node topology match SOMS exactly, or should it adapt to the actual sensor network topology?

5. **Environmental memory**: Cumulative damage (thermal cycles, humidity exposure) is modeled but not yet integrated into the live monitoring loop. Priority?

---

## Contributing

See `CONTRIBUTING.md` for guidelines. Key points:
- One focused change per PR
- Include evidence tier for new data
- Follow `lower_snake_case.md` naming
- Use SI spacing (`10 kΩ`, `150 °C`)
- Test simulations before submitting
