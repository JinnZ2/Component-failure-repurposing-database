# scenario_engine

Substrate self-awareness calibration playground.

Plug-in module for `Component-failure-repurposing-database`.

## Purpose

Test whether an AI system can:

1. Read its own substrate state (simulated sensor stream)
2. Detect degradation/failure events
3. Query the component database for repurposing options
4. Make routing decisions
5. Log decisions as **falsifiable claims**
6. Receive actual outcome and validate/invalidate the claim
7. Update internal model based on claim accuracy

## Architecture

```
scenario_engine/
├── scenarios/        # deterministic event generators
│   ├── thermal_events/
│   ├── power_events/
│   ├── mechanical_events/
│   ├── cascade_events/
│   └── environmental_events/
├── runner/           # event dispatcher + state machine
├── claims/           # CLAIM_TABLE.substrate.json schema + writer
├── validators/       # predicted vs actual outcome checker
├── docs/             # interface contracts, falsifiability spec
└── tests/            # self-tests (stdlib unittest)
```

## Design constraints

- Python stdlib only
- No external dependencies
- All claims falsifiable
- All outcomes deterministic and reproducible
- Phase 1: pure software, no hardware required
- Phase 2: same interface, real sensor stream
- Phase 3: cascade and edge case stress

## Quick start

```python
from scenario_engine.runner import ScenarioRunner
from scenario_engine.scenarios.thermal_events import HeatSpikeLocalized
from scenario_engine.claims import ClaimWriter
from scenario_engine.validators import OutcomeChecker

scenario = HeatSpikeLocalized(seed=42)
runner = ScenarioRunner(scenario)
writer = ClaimWriter(path="claims_log.json")

for reading in runner.stream():
    # AI sees the reading and may file a claim
    if reading.value > 80.0:
        writer.file_claim(
            scenario_id=scenario.id,
            t_made=reading.t,
            prediction_type="component_will_fail",
            prediction={"sensor_id": reading.sensor_id, "by_t": reading.t + 5.0},
            falsifiability={"check": "component_failure_before_t",
                            "sensor_id": reading.sensor_id,
                            "deadline": reading.t + 5.0},
        )

checker = OutcomeChecker(scenario.ground_truth())
for verdict in checker.evaluate(writer.claims()):
    print(verdict)
```

Run the demo end-to-end:

```
python -m scenario_engine
```

Run the self-tests:

```
python -m unittest discover -s scenario_engine/tests -v
```

## What this is not

- Not an AI alignment framework
- Not a consciousness experiment
- Not a resilience narrative
- Not optimization theater

This is a calibration loop. The AI reads state, predicts outcome,
gets graded against physics. If predictions don't match outcomes,
the model is wrong. That's the whole mechanism.

## License

MIT (inherits from parent repository).
