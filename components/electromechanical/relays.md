# Relays — Failure & Repurposing Specification

**Status:** Stub  
**Validation Level:** Literature Backed  
**Last Updated:** 2026-04-08

---

## Component Overview

```yaml
component_type: relay
original_function: Electrically controlled mechanical switch for power or signal routing
types:
  - Electromagnetic (SPST, SPDT, DPDT)
  - Reed relay
  - Solid-state (SSR)
  - Latching relay
coil_voltage: 3.3V, 5V, 12V, 24V, 48V
contact_rating: 1–30A at 250 VAC typical
coil_resistance: 50–1000Ω depending on voltage
mating_cycles: 100k–10M mechanical; 10k–500k electrical
```

---

## Failure Mode Analysis

### Failure Mode 1: Contact Welding

- **Cause:** Arc erosion and fusion during high-current switching
- **Frequency:** 35% of relay failures
- **Characteristics:**
  - Contacts permanently fused closed
  - Mechanical movement blocked or absent
  - Coil function may be preserved
  - Contact resistance near zero

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Permanent Jumper | High | Welded contacts provide reliable fixed connection; original current rating maintained |
| Electromagnetic Actuator | High | Coil preserved; usable for reed switch actuation, magnetic sensing, inductive coupling |
| Inductance Element | Medium | Coil as inductor; mH range; DC resistance in ohms |

**Implementation (Electromagnetic Actuator):**
```
Apply DC to coil → Generate magnetic field
Use for:
  - Reed switch actuation at distance
  - Magnetic field generation for sensing
  - Inductive coupling to nearby coil
Coil inductance: typically 10–500mH
Field strength: depends on distance and core
```

### Failure Mode 2: Coil Failure (Open)

- **Cause:** Thermal overstress, wire corrosion, mechanical damage
- **Frequency:** 25% of failures
- **Characteristics:**
  - Coil resistance infinite (open circuit)
  - Contacts rest in spring-return position
  - Manual actuation of mechanism still possible

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Mechanical Switch | Medium | Manually actuate contact mechanism; force required 5–50g |
| Antenna Coil | Medium | Coil winding usable as RF element; frequency range 1–100 MHz |
| Spacer / Mounting Element | High | Mechanical form factor preserved |

### Failure Mode 3: Contact Erosion (High Resistance)

- **Cause:** Repeated arcing, oxidation of contact surfaces
- **Frequency:** 25% of failures
- **Characteristics:**
  - Contact resistance increases 10–1000×
  - Pitting visible on contact surfaces
  - Mechanical action preserved

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Variable Resistor | Low | Resistance varies with contact pressure; crude but repeatable |
| Signal-Level Switch | Medium | Low-current signals (<10 mA) still switch cleanly |
| Environmental Indicator | Medium | Erosion rate correlates with switching history; lifecycle tracker |

### Failure Mode 4: Spring Fatigue

- **Cause:** Millions of mechanical cycles, material aging
- **Frequency:** 15% of failures
- **Characteristics:**
  - Contacts don't fully open or close
  - Reduced contact force
  - Bounce characteristics change

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Low-Force Switch | Medium | Reduced spring force makes it sensitive to light contact |
| Vibration Sensor | Low | Weakened spring causes bounce on vibration; detectable via contact chatter |

---

## Environmental Interaction Matrix

| Condition | Observed Effect | Repurpose Impact | Notes |
|---|---|---|---|
| High Temperature | Coil resistance increases; spring temper changes | Thermal indicator via coil resistance | Detectable with DMM |
| High Humidity | Contact corrosion accelerates | Humidity sensor via contact resistance | Requires calibration |
| Vibration | Contact bounce; mechanical fatigue | Vibration detector | Chatter pattern analysis |
| Dust/Contamination | Contact resistance increases | Environmental exposure indicator | Sealed relays resistant |
| Arc Erosion (Electrical) | Contact material transfer | Lifecycle tracking | Correlates with switch count |

---

## Testing Procedures

- **Contact Resistance:** Measure with contacts closed; normal <50 mΩ; failure >200 mΩ
- **Coil Resistance:** Measure DC resistance; normal = rated ±10%; open = >10 MΩ; shorted = <10% nominal
- **Pull-In Voltage:** Apply increasing voltage; contacts should close at ≤75% rated coil voltage
- **Mechanical Cycle Test:** Actuate 100 cycles; listen/measure for consistent operation

---

## AI Integration Notes

```yaml
ml_features:
  contact_resistance_trend: [time_series]
  coil_impedance: [dc_resistance, inductance]
  bounce_duration_ms: [per_cycle_measurement]
  arc_energy_cumulative: estimated_from_load
monitoring_frequency: every_1000_cycles
failure_prediction_model: "contact_welding_probability = f(current, cycle_count, load_type)"
```
