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

### Placeholders

An annotator sets every axis to one of its values, or to a placeholder. The
placeholders are the payload of E1, not error states.

"No value fits" is four findings wearing one label, and they imply four
different repairs. An annotator who can only say `FAIL` cannot tell you which
one they hit, so E1 cannot distinguish a missing *value* from a missing *axis*.

| Placeholder | Means | Repair it implies |
|-------------|-------|-------------------|
| `?` | Not judged yet | Annotate it |
| `GAP:VALUE` | Axis is right, its value list is too short | Add a value to that axis |
| `GAP:AXIS` | No axis captures the property at all | Add an eighth axis |
| `GAP:DEF` | Axis is ambiguous; two readings disagree here | Tighten the definition |
| `GAP:UNKNOWN` | A real quantity, not yet determinable | Measure it |
| `FAIL` | Legacy umbrella | Re-annotate as a `GAP:*` kind |

Every placeholder carries free text in `notes[<axis>]`. **A placeholder without
a note is not evidence of anything** — it records that someone was stuck, not
what they were stuck on.

```json
{"name": "entropy",
 "axes":  {"transfer": "GAP:VALUE"},
 "notes": {"transfer": "dS = d_eS + d_iS; flux and production are separate
           terms and neither DEBIT_CREDIT nor EQUILIBRATE covers both"}}
```

Placeholders are excluded from E2 scoring, as is any value not legal on its
axis — a typo is not a sentinel, and left unchecked it would enter the
contingency table as a real level.

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
| `ERASE` | Discarding it dissipates — Landauer, `kT ln 2` per bit as a quasi-static *bound*, not a price. See Open Questions | A flag overwritten each tick |
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

- **`transfer` assumes one mode per quantity. Entropy falsifies that.**
  📚 Literature Supported — Evidence Tier 2. Classical non-equilibrium
  thermodynamics splits the entropy balance into two simultaneous terms
  (de Groot & Mazur): `dS = d_eS + d_iS`, where `d_eS` is entropy *exchanged*
  across the boundary — signed, and sum-preserving, so `DEBIT_CREDIT` — and
  `d_iS ≥ 0` is entropy *produced* internally, which is a source term with no
  counterparty at all. Entropy is not missing a value. It needs `DEBIT_CREDIT`
  **and** a production term at the same time.

  This generalises past entropy: any quantity whose balance equation carries a
  source or sink has the same shape — mass under chemical reaction, charge
  under pair production, and every `PRODUCIBLE` quantity in this repository.
  So the repair is structural, not a fifth value: either `transfer` becomes a
  set rather than a scalar, or it splits into an `exchange` axis and a
  `production` axis. Annotate as `GAP:VALUE` on `transfer` until this is
  settled, and note which term is missing.

- **`cost` conflates a class with a magnitude.** 📚 Literature Supported —
  Evidence Tier 2. `ERASE` is written as though Landauer's `kT ln 2` were a
  fixed price. It is a bound attained only quasi-statically. In finite time
  the achievable cost rises with the inverse of the time budget: for slowly
  driven systems weakly coupled to a bath, `Q ≥ kT(ln 2 + π²/4Γτ)`; beyond
  weak coupling Rolandi & Perarnau-Llobet give
  `Q ≥ kT ln 2 + a·τ_Pl/τ + O(1/Γ²τ²)` with `a ≈ 2.579` and `τ_Pl = ℏ/kT`.
  A categorical axis cannot express "costs more if you do it faster". Either
  `cost` names only the dominant operation and the magnitude belongs to a
  separate quantity, or the axis is under-specified. For a repurposing
  database this is not academic: a degraded part re-tasked as a sensor is
  usually being read *faster* than its replacement cycle, which is exactly
  the regime where the finite-time penalty bites.
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

## References

Evidence Tier 2 (Literature) for the two Open Questions above.

| Source | Bears on |
|--------|----------|
| S. R. de Groot & P. Mazur, *Non-Equilibrium Thermodynamics*, North-Holland 1962 (Dover reprint 1984) | The `dS = d_eS + d_iS` split: entropy flux `J_s` versus entropy production `σ ≥ 0` |
| A. Rolandi & M. Perarnau-Llobet, "Finite-time Landauer principle beyond weak coupling", *Quantum* **7**, 1161 (2023). [arXiv:2211.02065](https://arxiv.org/abs/2211.02065) | Finite-time correction to the erasure bound at strong coupling |
| R. Landauer, "Irreversibility and heat generation in the computing process", *IBM J. Res. Dev.* **5**(3), 183–191 (1961) | Origin of the `kT ln 2` bound |

⚠️ Provenance caveat: this environment's egress allowlist blocks direct
retrieval from arxiv.org, quantum-journal.org and pmc.ncbi.nlm.nih.gov, so the
above was assembled from search results rather than from the papers
themselves. Title, venue, volume and year for the Rolandi & Perarnau-Llobet
paper were cross-confirmed across two independent searches; the Landauer and
de Groot & Mazur entries are standard references given from established
knowledge and were **not** machine-verified here. Confirm before citing
onward, and do not promote any of this to a higher evidence tier on the
strength of this file alone.

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

E2's machinery is known good, which the zero-result runs above cannot show. On
a 40-row synthetic worksheet carrying a planted dependency — `dimension` set as
a strict function of `extensivity` — it recovers `U(A|B) = U(B|A) = 1.000` at
p = 0.0005 and returns `REDUNDANT — collapse these`, while the other 20 pairs
come back independent. So the empty result on real bindings is data starvation,
not a broken instrument.

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
