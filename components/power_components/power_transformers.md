# Power Transformers — Failure & Repurposing Specification

**Status:** Stub  
**Validation Level:** Literature Backed  
**Last Updated:** 2026-04-08

---

## Component Overview

```yaml
component_type: power_transformer
original_function: Voltage conversion and galvanic isolation in power circuits
types:
  - Mains transformer (50/60 Hz, laminated core)
  - Switching transformer (20 kHz–1 MHz, ferrite core)
  - Flyback transformer
  - Toroidal transformer
power_rating: 1 VA–5 kVA
primary_voltage: 85–265 VAC (universal) or fixed mains
secondary_voltage: 3.3V–48V typical
isolation_voltage: 1–4 kV typical
```

---

## Failure Mode Analysis

### Failure Mode 1: Winding Open Circuit

- **Cause:** Thermal overstress, wire corrosion, physical damage
- **Frequency:** 35% of power transformer failures
- **Characteristics:**
  - Affected winding reads open (>10 MΩ)
  - Other windings may still function
  - Core and mechanical structure preserved

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Single-Winding Inductor | High | Remaining winding(s) with core provide high-quality inductance; mH–H range |
| EMI Common-Mode Choke | Medium | Core properties preserved; effective up to rated frequency |
| Isolation Barrier | High | Galvanic isolation between primary and secondary maintained mechanically |
| Core Material Harvesting | Medium | Laminated or ferrite core reusable for custom magnetics |

### Failure Mode 2: Shorted Turns

- **Cause:** Insulation breakdown from heat, voltage stress, moisture
- **Frequency:** 30% of failures
- **Characteristics:**
  - Reduced turns ratio; incorrect output voltage
  - Increased current draw; excessive heating
  - Core may still be functional
  - Detectable via impedance measurement

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Heating Element | Medium | Shorted turns create resistive loss; predictable heat output at known current |
| Low-Ratio Transformer | Low | Reduced turns ratio may match a different voltage requirement |
| Current Transformer | Medium | Shorted secondary acts as single-turn CT; monitor primary current |

### Failure Mode 3: Core Saturation / Damage

- **Cause:** DC bias, overcurrent, physical shock (ferrite cracking)
- **Frequency:** 20% of failures
- **Characteristics:**
  - Reduced inductance
  - Higher magnetizing current
  - Audible hum or buzz (laminated cores)
  - Visible cracks (ferrite cores)

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| EMI Absorber | Medium | Damaged core still absorbs RF energy; ferrite fragments usable |
| Mechanical Mass / Damper | High | Heavy core useful as vibration dampener or ballast |
| Low-Frequency Inductor | Low | Reduced but non-zero inductance; usable at lower frequencies |

### Failure Mode 4: Insulation Breakdown (Inter-Winding)

- **Cause:** Moisture ingress, voltage stress, aging
- **Frequency:** 15% of failures
- **Characteristics:**
  - Reduced isolation voltage between windings
  - Leakage current primary-to-secondary
  - May still function at lower voltages

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Low-Voltage Transformer | Medium | Reduced isolation still adequate for <50V applications |
| Autotransformer | Medium | Connect windings in series; no isolation needed for some applications |
| Coupled Inductor | Medium | Magnetic coupling preserved; useful for energy storage converters |

---

## Environmental Interaction Matrix

| Condition | Observed Effect | Repurpose Impact | Notes |
|---|---|---|---|
| High Temperature | Insulation ages faster; core loss ↑ | Heating element output ↑ | Derate above rated temp |
| High Humidity | Insulation breakdown accelerates | Leakage current ↑ | Moisture ingress indicator |
| Vibration | Lamination loosening; ferrite cracking | Audible indicator | Hum/buzz changes with load |
| DC Bias | Core saturation | Reduced inductance | Still usable at lower levels |

---

## Safety Considerations

```yaml
safety:
  electrical_shock:
    level: high_voltage
    maximum_voltage: Mains voltage (120/240 VAC)
    isolation_status: may_be_compromised
    required_precautions: >
      ALWAYS assume insulation may be degraded.
      Test isolation before applying mains voltage.
      Use GFCI/RCD protection.
      Never rely on failed transformer for safety isolation.
  fire_risk:
    level: moderate
    conditions: Shorted turns cause localized heating
    mitigation: Thermal fuse on core; overcurrent protection
```

---

## Testing Procedures

- **Winding Resistance:** DMM across each winding; compare to expected (wire gauge × turns × length)
- **Turns Ratio:** Apply low AC voltage to primary; measure secondary; compare to nameplate ratio
- **Insulation Resistance:** 500V megohmmeter between windings and to core; normal >100 MΩ
- **Core Loss:** Measure no-load primary current; excessive = shorted turns or saturated core
- **Inductance:** LCR meter on primary (secondary open); compare to expected for core type
