# Switches — Failure & Repurposing Specification

**Status:** Stub  
**Validation Level:** Theoretical  
**Last Updated:** 2026-04-08

---

## Component Overview

```yaml
component_type: switch
original_function: Manual or mechanical circuit control
types:
  - Tactile (momentary)
  - Toggle (latching)
  - Slide
  - Rotary
  - Micro-switch (snap-action)
  - DIP switch
contact_rating: 0.1–20A depending on type
voltage_rating: 12–250V
mechanical_life: 10k–10M cycles
```

---

## Failure Mode Analysis

### Failure Mode 1: Contact Bounce / Degradation

- **Cause:** Contact oxidation, material wear, spring fatigue
- **Frequency:** 40% of switch failures
- **Characteristics:**
  - Excessive bounce duration (>10 ms)
  - Intermittent contact
  - Increased contact resistance

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Noise Source | Medium | Contact bounce as entropy for random number generation |
| Vibration-Activated Trigger | Medium | Degraded contact closes more easily under vibration |
| Debounce Testing Standard | Low | Known-bad switch for testing debounce algorithms |

### Failure Mode 2: Mechanical Failure (Stuck Open/Closed)

- **Cause:** Physical damage, contamination, welded contacts
- **Frequency:** 35% of failures
- **Characteristics:**
  - No mechanical actuation or permanent closure
  - May still have partial travel

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Fixed Jumper (Stuck Closed) | High | Permanent connection; current rating preserved |
| Spacer / Mounting Point (Stuck Open) | High | Physical form factor maintained |
| Strain Gauge Mount | Low | Partial travel under extreme force may indicate strain |

### Failure Mode 3: Contact Resistance Increase

- **Cause:** Oxide buildup, contamination, plating wear-through
- **Frequency:** 25% of failures
- **Characteristics:**
  - Contact resistance >1 Ω
  - Still mechanically functional
  - Resistance varies with contact pressure

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Pressure-Variable Resistor | Low | Resistance varies with actuation force; crude force sensor |
| Signal-Level Switch | Medium | Low-current signals still switch; unsuitable for power |
| Environmental Indicator | Medium | Oxide buildup rate tracks humidity/contamination exposure |

---

## Environmental Interaction Matrix

| Condition | Observed Effect | Repurpose Impact | Notes |
|---|---|---|---|
| Dust/Contamination | Contact resistance ↑ | Environmental exposure indicator | Sealed types more resistant |
| High Humidity | Oxide formation accelerates | Humidity correlation | Measurable via resistance |
| Vibration | Contact chatter | Vibration detector | Bounce frequency analysis |
| Temperature Cycling | Spring temper changes | Thermal stress history | Actuation force changes |

---

## Testing Procedures

- **Contact Resistance:** Normal <100 mΩ; failure >1 Ω
- **Actuation Force:** Measure with force gauge; should match datasheet ±20%
- **Bounce Test:** Oscilloscope on contact; normal <5 ms; failure >10 ms
- **Cycle Test:** 100 actuations; consistent resistance and feel
