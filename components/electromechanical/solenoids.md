# Solenoids — Failure & Repurposing Specification

**Status:** Stub  
**Validation Level:** Theoretical  
**Last Updated:** 2026-04-08

---

## Component Overview

```yaml
component_type: solenoid
original_function: Linear electromechanical actuator (electrical → linear motion)
types:
  - Push-type
  - Pull-type
  - Rotary solenoid
  - Proportional solenoid
coil_voltage: 5V, 12V, 24V, 48V
current_draw: 0.1–5A
stroke: 2–50mm
force: 0.1–50N
duty_cycle: 10–100% depending on design
```

---

## Failure Mode Analysis

### Failure Mode 1: Coil Burnout (Open)

- **Cause:** Excessive duty cycle, thermal runaway, voltage spike
- **Frequency:** 40% of solenoid failures
- **Characteristics:**
  - Infinite coil resistance
  - No magnetic actuation
  - Plunger free to move mechanically
  - Core material preserved

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Mechanical Plunger / Spring Return | Medium | Manual actuation still works; spring provides restoring force |
| Ferromagnetic Core | High | Iron core usable as EMI absorber, magnetic field concentrator |
| Mechanical Spacer / Mount | High | Form factor preserved for PCB or chassis mounting |

### Failure Mode 2: Plunger Stuck (Mechanical Jam)

- **Cause:** Corrosion, contamination, mechanical deformation
- **Frequency:** 30% of failures
- **Characteristics:**
  - Coil function preserved
  - Plunger does not move
  - Magnetic field still generated

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Static Electromagnet | High | Coil generates field without mechanical motion; use for holding, sensing |
| Inductor | Medium | Coil with iron core; inductance in mH–H range |
| Proximity Sensor | Medium | Magnetic field detectable by Hall sensor or reed switch at distance |

### Failure Mode 3: Weak Pull / Force Degradation

- **Cause:** Partial coil shorts, spring fatigue, demagnetization
- **Frequency:** 30% of failures
- **Characteristics:**
  - Reduced force output
  - Slower actuation
  - May not fully extend/retract

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Low-Force Actuator | Medium | Still usable for light-duty tasks; paper feed, flag actuation |
| Vibration Generator | Medium | Incomplete actuation under PWM creates vibration |
| Current Sensor | Low | Reduced coil performance; inductance change detectable under load |

---

## Environmental Interaction Matrix

| Condition | Observed Effect | Repurpose Impact | Notes |
|---|---|---|---|
| High Temperature | Coil resistance increases; force decreases | Better as inductor (higher R) | Derate above 60°C |
| High Humidity | Corrosion of plunger and bore | Mechanical jam likelihood ↑ | Sealed types resistant |
| Vibration | Mechanical wear accelerates | Force sensor potential | Detectable via actuation change |
| Dust | Plunger contamination | Jam risk increases | Keep bore clean |

---

## Testing Procedures

- **Coil Resistance:** DMM across terminals; compare to datasheet ±15%
- **Pull Force:** Apply rated voltage; measure force with spring scale; compare to datasheet
- **Stroke Test:** Measure plunger travel; should be full rated stroke
- **Duty Cycle Test:** Run at rated duty; monitor temperature; should not exceed thermal limits
