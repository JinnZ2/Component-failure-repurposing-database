# scenarios/_attic

Initial scaffold scenarios, superseded by the canonical 7. Preserved for
reference; not imported by the engine, not registered in `REGISTRY`.

| File | Notes |
|---|---|
| `heat_spike_localized.py` | Single-IC thermal spike + ambient comparators. |
| `ambient_drift.py` | Shared-environment drift across multiple thermistors. |
| `thermal_runaway_cascade.py` | Fixed-delay propagation along a chain. |
| `voltage_sag.py` | Brief transient sag (no permanent failure). |
| `brownout.py` | MCU reset window during sustained brownout. |
| `ground_loop.py` | 60 Hz common-mode shift on a shared ref. |
| `vibration_resonance_baseline.py` | Pure mechanical sweep; **superseded by canonical `vibration_resonance.py` with cross-substrate coupling**. |
| `impact_shock.py` | Half-sine pulse + crystal-rated failure. |
| `fatigue_cycling.py` | Miner's-rule fatigue under steady cycling. |
| `single_component_then_propagation.py` | Primary → secondary with fixed delay. |
| `shared_substrate_failure.py` | All-at-once trace-crack on a PCB zone. |
| `timing_drift_cascade.py` | Drifting reference; worst-margin links fail first. |
| `humidity_intrusion.py` | Insulation-resistance fall under high RH. |
| `em_interference_baseline.py` | ADC modulation during EM burst; **superseded by canonical `em_interference.py` with drift-vs-noise discrimination**. |
| `radiation_burst.py` | SEU + SEL with bounded recovery window. |

These import `from ..base import ...` and `from .._helpers import ...`,
which still resolve correctly because both `base.py` and `_helpers.py`
remain at `scenarios/`.
