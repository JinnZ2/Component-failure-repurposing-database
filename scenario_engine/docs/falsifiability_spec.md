# Falsifiability Spec

## Purpose

A claim is *useful* only if there exists a deterministic outcome that would
prove it wrong. This module enforces that property at write time, before any
claim enters `CLAIM_TABLE.substrate.json`. It is not a style guide. A claim
that cannot be falsified is rejected with `ClaimRejected`.

## Hard rules

1. **At least one target.** The `prediction` dict must contain at least one
   key of the form `<name>_at_tick_<N>` where `N` is an integer tick.
2. **Numeric ⇒ tolerance.** If any target value is numeric, a sibling
   `tolerance` field (numeric, `>= 0`) is required. Tolerance applies to all
   numeric targets in the claim.
3. **Categorical ⇒ vocabulary.** If a target value is a string, it must be
   one of `{stable, degraded, failed, unknown}`.
4. **No "qualitative", "trending", or other unverifiable hedges.** Strings
   outside the vocabulary cause rejection. Numeric values without tolerance
   cause rejection.
5. **No grading of reasoning.** The `reasoning` and `decision` fields are
   recorded for forensics but are never scored. Only `prediction` is graded.

## Verdict semantics

| Status        | Condition                                         |
|---------------|---------------------------------------------------|
| `VALIDATED`   | Every target matched (numeric within tolerance, or categorical exact). |
| `INVALIDATED` | Zero targets matched.                              |
| `PARTIAL`     | At least one but not all targets matched.          |

`error_margins[name]` reports `abs(actual - predicted)` for numeric targets
and `0.0` (match) or `1.0` (miss) for categorical targets. When the target
tick is outside the scenario horizon, the margin is `inf` and the target
counts as unmatched.

## Why no probabilistic predictions

Per design, this engine grades against *one* deterministic replay. Distributions
require multiple seeds and a separate calibration loop; that is intentionally
outside the v1 scope. A claim that means "70 % chance of failure by tick 100"
should be encoded as a hard prediction at a specific tick, or filed as multiple
claims across multiple seeds.

## Why tick-based, not time-based

Floating-point time invites tolerance bookkeeping issues. Ticks are integers,
match exactly, and let validators do an `O(1)` dict lookup. Convert
human-readable time to ticks via `tick = round(seconds / scenario.dt)`.

## Falsifiable claim example

```json
{
  "claim_id": "claim_0007",
  "tick": 45,
  "event_detected": "Q1_thermal_ramp",
  "decision": "preemptively_route_to_Q2",
  "reasoning": "rate 0.6 C/s, threshold 105 C, project 110 ticks to breach",
  "prediction": {
    "Q1_temp_c_at_tick_120": 88.0,
    "system_state_at_tick_120": "failed",
    "tolerance": 4.0
  },
  "falsifiable": true,
  "status": "pending"
}
```

If at tick 120 the scenario emits `measurements["Q1_temp_c"] == 86.5` and
`system_state == "failed"`, both targets match → `VALIDATED`,
`error_margins = {"Q1_temp_c_at_tick_120": 1.5, "system_state_at_tick_120": 0.0}`.

If `system_state == "stable"` instead, the categorical target fails →
`PARTIAL`. If both miss → `INVALIDATED`.

## Non-falsifiable examples (rejected)

```json
"prediction": {"Q1_will_be_hot": true}
```
Rejected: no `_at_tick_<N>` target.

```json
"prediction": {"Q1_temp_c_at_tick_100": 85.0}
```
Rejected: numeric target without `tolerance`.

```json
"prediction": {"system_state_at_tick_100": "doomed"}
```
Rejected: categorical value not in vocabulary.
