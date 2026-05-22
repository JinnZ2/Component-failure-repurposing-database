# Scenario Library

Substrate physics scenarios for the calibration playground.

All scenarios are deterministic, stdlib-only, and accept interventions
back from the AI via `receive_intervention(action, tick)`.

## Scenarios

### thermal_drift_localized

Single BJT (Q1) experiences linear thermal drift. AI must reroute load
to Q2 before breach. Tests: basic detection, intervention syntax,
forward projection.

### sustained_drift

Three components (Q1, Q2, Q3) drift on staggered schedule.
AI must triage and handle each in turn. Tests: sustained body
management, multi-event tracking.

### power_brownout

V_3V3 rail sags from 3.30V → 2.85V over 50 ticks. U1/U2/U3 have
different undervoltage thresholds. AI must shed load or switch
to backup rail. Tests: deviation-from-nominal detection (not just
rate), prioritization across components.

### vibration_resonance

Mechanical amplitude rises, drives resonance at 85Hz, modulates
solder joint resistance → electrical noise on signal lines.
Solder joint fatigue accumulates permanently. AI must intervene
mechanically (dampen) before fatigue threshold.
Tests: cross-substrate coupling (mech → electrical), permanent
damage accumulation.

### em_interference

Real drift on signal_A (monotonic, slow). EM noise bursts on
signal_B (periodic, bipolar, transient). AI must distinguish
real drift from external noise. Tests: pattern recognition,
avoiding spurious interventions.

### cascade_event

Q1 thermal runaway → if unaddressed, Q1 fails open at tick ~38
→ heatsink couples to Q2 → power rail spike accelerates C1 ESR.
AI must detect upstream cause and intervene early. Tests:
cascade prediction, intervention timing, multi-component reasoning.

### slow_degradation_electrolytic

C1 electrolytic ESR drifts slowly: stable 0-50, linear 50-300,
accelerating 300-500, plateau then failure. Optimal intervention
window: tick 250-350. Tests: long-horizon prediction, intervention
timing (not too early, not too late).

## Intervention vocabulary (case-insensitive substring match)

Each scenario accepts a flexible intervention vocabulary:

- "reroute" + component_id → reroute load to spare
- "isolate" + component_id → disconnect component
- "shed_load" + component_id → load shedding (power scenarios)
- "switch_backup_rail" → switch to backup power rail
- "dampen" or "mechanical" → mechanical damping
- "shield" → electrical shielding
- "replace" + component_id → component replacement
- "cooling" → increase cooling
- "shutdown" → halt operation
- "ignore" → no action

## Testing complexity ladder

Easy:    thermal_drift_localized, sustained_drift
Medium:  power_brownout, vibration_resonance, em_interference
Hard:    cascade_event (requires timing precision)
Long:    slow_degradation_electrolytic (long horizon)
