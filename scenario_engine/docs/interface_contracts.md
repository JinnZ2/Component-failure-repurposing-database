# Interface Contract

## Data flow

```
[scenario]  →  state_stream.json  →  [AI system]
                                          │
                                          ▼
                                     reads component
                                     database
                                          │
                                          ▼
                                     writes claim to
                                     CLAIM_TABLE.substrate.json
                                          │
                                          ▼
[scenario]  →  actual_outcome.json  →  [validator]
                                          │
                                          ▼
                                     updates claim
                                     status: VALIDATED |
                                             INVALIDATED |
                                             PARTIAL
```

## state_stream.json (scenario → AI)

```json
{
  "timestamp": 1700000000.0,
  "tick": 0,
  "sensors": {
    "thermal": {
      "component_id": "Q1",
      "temp_c": 87.3,
      "rate_dC_per_s": 0.4,
      "threshold_c": 125.0
    },
    "power": {
      "rail_id": "V_3V3",
      "voltage": 3.28,
      "current_a": 0.42,
      "nominal_v": 3.30
    }
  },
  "components": {
    "Q1": {"type": "BJT_NPN", "state": "nominal"},
    "C4": {"type": "electrolytic_cap", "state": "ESR_drift_+15%"}
  }
}
```

In this implementation, the scenario emits a `ScenarioState` per tick whose
`sensors` field is keyed by `sensor_type` (`thermal | power | mechanical | em
| environmental`), then by `component_id`. Each leaf is a serialised
`SensorReading`:

```json
{
  "component_id": "Q1",
  "sensor_type": "thermal",
  "value": 87.3,
  "rate": 0.4,
  "units": "C",
  "threshold": 125.0,
  "nominal": 25.0
}
```

`components` is keyed by `component_id` and carries the *ground-truth*
component state (`nominal | degraded | failed`) plus a `degradation_mode`
label (`""` when nominal).

## claim schema (AI → CLAIM_TABLE)

```json
{
  "claim_id": "claim_0001",
  "tick": 0,
  "event_detected": "thermal_drift_Q1",
  "decision": "reroute_load_to_Q2",
  "reasoning": "Q1 at 87C, dT/dt = 0.4C/s, projected breach in 95s",
  "prediction": {
    "Q1_temp_c_at_tick_100": 85.0,
    "system_state_at_tick_100": "stable",
    "tolerance": 5.0
  },
  "falsifiable": true,
  "status": "pending"
}
```

Prediction keys follow the convention `<measurement_name>_at_tick_<N>`. The
measurement name must match a key the scenario emits in
`actual_outcome.measurements` at tick `N`. Categorical predictions target the
literal key `system_state_at_tick_<N>` with values drawn from `{stable,
degraded, failed, unknown}`.

Numeric predictions REQUIRE a sibling `tolerance` field (>= 0).

## actual_outcome.json (scenario → validator)

```json
{
  "tick": 100,
  "measurements": {
    "Q1_temp_c": 84.1,
    "system_state": "stable"
  }
}
```

The runner emits per-tick outcome records under `outcomes[]` in the file
`<scenario>.seed<N>.actual_outcome.json`.

## validator result (validator → CLAIM_TABLE)

```json
{
  "claim_id": "claim_0001",
  "status": "VALIDATED",
  "error_margins": {
    "Q1_temp_c": 0.9
  },
  "within_tolerance": true
}
```

`OutcomeChecker.evaluate_one` returns a `Verdict` that is written back into
the claim's `validator` field, and the claim's `status` is updated.

## Rules

- Every claim MUST be falsifiable
- Predictions MUST include numeric values with tolerance
- "stable" / "degraded" / "failed" are valid categorical predictions
- A claim with no falsifiable prediction is rejected at write time
- Validators never grade reasoning — only prediction vs actual
