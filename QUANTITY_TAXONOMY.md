# Quantity Taxonomy

Spec under test by [`experiments/sims/taxonomy_lab.py`](experiments/sims/taxonomy_lab.py).

**Validation level:** `theoretical` — Evidence Tier 1 (physics compliance). ⚠️ Theoretical.
No hand-annotated corpus exists yet, so none of the three falsification
experiments has produced a usable result. See [Status](#status).

---

## The Claim

Every binding in real code reduces, without remainder, to exactly three parts:

```
binding  ->  (BINDING_TOPOLOGY, QUANTITY_TYPE, RESIDUE)
```

| Part | Recovered by | Judgement required |
|------|--------------|--------------------|
| `BINDING_TOPOLOGY` | Static analysis of the source | None — mechanical |
| `QUANTITY_TYPE` | 7 independent axes, one value each | Human annotator |
| `RESIDUE` | Whatever is left over | Claimed inert |

The claim is falsifiable in three separate ways, one per component. It is
**not** a claim that these axes are useful. It is a claim that they are
*sufficient* (nothing untypable), *independent* (none derivable from another),
and *complete* (nothing load-bearing left in residue).

---

## Part 1 — Binding Topology

Recovered mechanically per `(file, scope, name)`. No annotation.

| Field | Meaning |
|-------|---------|
| `scope`, `scope_kind` | `module`, `func:<name>`, or `class:<name>` |
| `first_write`, `last_read` | Line numbers; `last_read = -1` if never read |
| `n_writes`, `n_reads` | Write and read counts |
| `lifetime` | `max(0, last_read - first_write)` |
| `augmented` | Participates in `x += ...` — accumulator shape |
| `is_param` | Bound as a function parameter |
| `is_loop_var` | Bound as a `for` target |
| `literal_kinds` | Observed right-hand-side literal types |

Topology is descriptive only. It constrains the quantity type but does not
determine it — if it did, the annotation step would be unnecessary and the
claim would collapse into static analysis.

---

## Part 2 — The Seven Axes

Machine-readable form, authoritative against `AXES` in the harness:

```yaml
axes:
  extensivity:  [EXTENSIVE, INTENSIVE, NONE]
  conservation: [CONSERVED, MONOTONE, PRODUCIBLE, NONE]
  domain:       [FLOORED, SIGNED, BOUNDED, CEILINGED, NONE]
  datum:        [ABSOLUTE, RELATIVE, NONE]
  dimension:    [DIMENSIONLESS, DIMENSIONED, NONE]
  transfer:     [DEBIT_CREDIT, COPY, CONSUME, EQUILIBRATE]
  cost:         [ERASE, COPY, TRANSFORM]
unjudged: "?"
untypable: "FAIL"
```

An annotator sets every axis to one of its values, or to `FAIL` when no value
fits. `FAIL` is the payload of experiment E1, not an error state.

### extensivity

*Test question: if you join two identical systems, does the value double?*

| Value | Definition | Example |
|-------|------------|---------|
| `EXTENSIVE` | Additive over subsystems; scales with system size | Charge, energy, a count of failed parts |
| `INTENSIVE` | Invariant under joining; a ratio or local property | Temperature, density, `health_score` |
| `NONE` | Not a magnitude at all | A component ID, a mode flag |

### conservation

*Test question: can the total change, and in which direction?*

| Value | Definition | Example |
|-------|------------|---------|
| `CONSERVED` | Total is invariant; movement only, never creation | `EnergyState.total_energy` under `COBOL:MOVE` |
| `MONOTONE` | Changes in one direction only | Entropy, elapsed time, a cycle counter |
| `PRODUCIBLE` | Freely created and destroyed | A cache entry, a buffered sample |
| `NONE` | Conservation is not defined for it | A label |

### domain

*Test question: which ends of the number line are reachable?*

| Value | Definition | Example |
|-------|------------|---------|
| `FLOORED` | Lower bound only, usually 0 | A count, a resistance |
| `SIGNED` | Unbounded both directions | A drift delta, an error term |
| `BOUNDED` | Both ends fixed | `health_score` ∈ 0.0–1.0, a probability |
| `CEILINGED` | Upper bound only | Fill level against a capacity |
| `NONE` | Not ordered | A label |

### datum

*Test question: is zero a fact about the world, or a choice?*

| Value | Definition | Example |
|-------|------------|---------|
| `ABSOLUTE` | Meaningful zero; ratios are meaningful | Kelvin, a count |
| `RELATIVE` | Arbitrary zero; only differences are meaningful | Celsius, a timestamp, a calibration offset |
| `NONE` | No zero | A label |

`RELATIVE` is the axis that catches unit-origin errors: adding two Celsius
readings is meaningless, adding two kelvin readings is not.

### dimension

*Test question: does the number change if you change units?*

| Value | Definition | Example |
|-------|------------|---------|
| `DIMENSIONLESS` | Pure number or ratio | `drift_pct`, a gain |
| `DIMENSIONED` | Carries units | `5 mA`, `150 °C`, `10 kΩ` |
| `NONE` | Not numeric | A label |

### transfer

*Test question: what happens to the source when the value moves to a target?*

| Value | Definition | Example |
|-------|------------|---------|
| `DEBIT_CREDIT` | Source decrements by exactly what the target gains | Energy under `COBOL:MOVE` |
| `COPY` | Source retains; target gains | A string, a reading broadcast to two plugins |
| `CONSUME` | Destroyed on use; no target retains it | A one-shot permit, a drawn-down reserve |
| `EQUILIBRATE` | Contact drives the two toward equality | Temperature across a thermal joint |

**No `NONE`.** This is a deliberate, load-bearing commitment: the taxonomy
asserts every binding has a transfer semantics. See [Predictions](#predictions).

### cost

*Test question: what does the dominant operation on this value cost, thermodynamically?*

| Value | Definition | Example |
|-------|------------|---------|
| `ERASE` | Discarding it dissipates — Landauer, `kT ln 2` per bit | A flag overwritten each tick |
| `COPY` | Duplication is the dominant cost | A propagated sensor reading |
| `TRANSFORM` | Conversion between representations dominates | An ADC count converted to °C |

**No `NONE`.** Same commitment as `transfer`.

---

## Part 3 — Residue

Residue is everything the first two parts do not capture: the *value* of a
label whose only job is to be distinguishable from other labels.

The claim: residue is **inert**. Only the edge — the fact that this name binds
to something distinct — carries meaning. The particular value does not.

Operational definition, which is what E3 tests: permute the values bound to
residue names. If observable behavior is unchanged, the residue was inert. If
behavior changes, the value smuggled ordering, indexing, or magnitude, and it
was never residue.

---

## Worked Examples

Drawn from this repository. Each is a hypothesis for annotation, not a settled
answer.

```yaml
- binding: EnergyState.total_energy      # vendor/cyclic/cyclic_interpreter.py
  extensivity:  EXTENSIVE
  conservation: CONSERVED                # verified: MOVE 30 takes 100/50 -> 70/80
  domain:       FLOORED                  # but see Open Questions — it goes negative
  datum:        ABSOLUTE
  dimension:    DIMENSIONED
  transfer:     DEBIT_CREDIT
  cost:         TRANSFORM

- binding: health_score                  # binary_sensor.md
  extensivity:  INTENSIVE
  conservation: NONE
  domain:       BOUNDED                  # 0.0-1.0
  datum:        ABSOLUTE
  dimension:    DIMENSIONLESS
  transfer:     COPY
  cost:         COPY

- binding: temperature_c                 # src/hardware_bridge_encoder.py
  extensivity:  INTENSIVE
  conservation: NONE
  domain:       SIGNED
  datum:        RELATIVE                 # Celsius: arbitrary zero
  dimension:    DIMENSIONED
  transfer:     EQUILIBRATE
  cost:         TRANSFORM

- binding: EnvironmentalMemory.thermal_cycles   # scenario_engine/environment/environment_state.py
  extensivity:  EXTENSIVE
  conservation: MONOTONE                 # cumulative damage never reverses
  domain:       FLOORED
  datum:        ABSOLUTE
  dimension:    DIMENSIONLESS
  transfer:     COPY
  cost:         ERASE

- binding: RepurposeReserve.value        # repurpose_controller.py
  extensivity:  EXTENSIVE
  conservation: MONOTONE                 # drawn down and decayed, never refilled
  domain:       FLOORED
  datum:        ABSOLUTE
  dimension:    DIMENSIONLESS
  transfer:     CONSUME
  cost:         TRANSFORM

- binding: component_id                  # "resistor_R1"
  extensivity:  NONE
  conservation: NONE
  domain:       NONE
  datum:        NONE
  dimension:    NONE
  transfer:     COPY
  cost:         ERASE
  residue:      the string itself
  # E3 on this one is oracle-sensitive: inert as a dict key, flagged the
  # moment it is printed. See Status.
```

---

## Falsification

Three experiments, three distinct ways the claim dies.

| Experiment | Kills the claim if | Reads |
|------------|--------------------|-------|
| **E1 Coverage** | Bindings recur that no axis value fits | `FAIL` count and the axes involved |
| **E2 Orthogonality** | An axis is fully determined by another | `U(A\|B) → 1.0` at p < 0.05 |
| **E3 Residue** | Permuting residue values changes behavior | Any `BEHAVIOR CHANGED` trial |

E2 measures the uncertainty coefficient `U(A|B) = (H(A) − H(A|B)) / H(A)`
against a shuffled null. `U = 1.0` means B fully determines A, so A is
redundant and the seven axes are really six.

### Predictions

Stated in advance, so confirmation is not retrofitted:

1. `transfer` and `cost` have no `NONE`, so pure labels must still be assigned
   one of each. If annotators consistently mark `FAIL` on those two axes for
   labels, the missing value is `NONE` and the axes are under-specified.
2. `extensivity` and `dimension` are expected to couple — `NONE` on one tends
   to accompany `NONE` on the other. Coupling short of `U = 1.0` is survivable;
   `U = 1.0` collapses them.
3. `datum: RELATIVE` should be rare and concentrated in temperature and
   timestamp bindings. If it is common, the axis is being over-applied.

---

## Open Questions

- **Entropy does not type cleanly.** It is `MONOTONE` and `EXTENSIVE`, but its
  transfer mode fits none of the four: heat flow moves entropy *and* produces
  it, so it is neither `DEBIT_CREDIT` (not sum-preserving) nor `EQUILIBRATE`
  (that is temperature, not entropy). This is a live E1 `FAIL` candidate.
- **`FLOORED` describes intent, not behavior.** `EnergyState.total_energy` is
  floored in principle but goes negative in practice when a decay rate exceeds
  1.0. Does the axis describe the quantity or the implementation? They diverge,
  and the taxonomy does not currently say which it types.
- **Axis values are unordered.** E2's entropy measures treat every axis as
  categorical, so `BOUNDED` and `FLOORED` are as distant as `BOUNDED` and
  `NONE`. If the domain values are actually a lattice, the statistics understate
  structure.
- **One value per axis.** Nothing yet handles a binding whose type changes
  across its lifetime — a slot that holds a raw ADC count, then a temperature.

---

## Status

Neither E1 nor E2 has produced data. Both require hand annotation, which does
not exist yet.

The harness's heuristic pre-typer is deliberately conservative and leaves most
axes unjudged: on 639 bindings extracted from `src/`, it typed `cost` on 1 and
`domain` on 4. Every one of the 21 axis pairs was consequently either skipped
for insufficient data or degenerate from a constant column — **zero scored
pairs**. The same held on the harness's own selftest.

So the cheapest experiment is gated on the most expensive input. To move:

```sh
python3 experiments/sims/taxonomy_lab.py extract worksheet.json src/*.py
# then annotate worksheet.json by hand: every axis, or FAIL
python3 experiments/sims/taxonomy_lab.py e1 worksheet.json
python3 experiments/sims/taxonomy_lab.py e2 worksheet.json
```

E2 needs ≥ 10 jointly-judged bindings per axis pair and at least two distinct
values in each column before it will score anything.

E3 is runnable now, and is the only experiment that needs no annotation beyond
naming the residue bindings. It has two known blind spots, in opposite
directions, and both were reproduced:

- **False `INERT`.** Permutation preserves the value multiset, so behavior
  depending only on the set — sorting, summing, `min`/`max` — is invisible.
  A program that sorts three residue labels and prints them is genuinely
  order-dependent, and E3 calls it inert on every trial.
- **False `LOAD-BEARING`.** The oracle is stdout equality, so a residue value
  that merely *reaches* the output is flagged even when no computation
  depends on it. The `component_id` example above demonstrates both halves:
  with `resistor_R1` used as a dict key and printed, E3 returns
  `LOAD-BEARING`; with the identical bindings used as keys only and never
  printed, the same permutations return `INERT`.

The second is the more dangerous, because it fires on exactly the bindings the
taxonomy nominates as residue. Reading it as a refutation would retire the
residue claim on evidence that is really about the display path. A sound E3
needs an oracle over computed state rather than stdout, or a rule that residue
values reaching output are excluded from the test.
