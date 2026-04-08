# Power Diodes — Failure & Repurposing Specification

**Status:** Stub  
**Validation Level:** Literature Backed  
**Last Updated:** 2026-04-08

---

## Component Overview

```yaml
component_type: power_diode
original_function: High-current rectification and power conversion
types:
  - Standard recovery (50 Hz/60 Hz rectification)
  - Fast recovery (switching power supplies)
  - Ultra-fast recovery (high-frequency converters)
packages:
  - DO-201AD, DO-41 (axial)
  - TO-220, TO-247 (stud mount)
  - D2PAK, DPAK (SMD power)
common_parts:
  - 1N5400 series (3A, 50–1000V)
  - 6A10 (6A, 1000V)
  - MUR series (fast recovery)
  - RHRP series (hyperfast)
voltage_rating: 50–1200V
current_rating: 3–60A
forward_voltage: 0.7–1.5V typical
```

---

## Failure Mode Analysis

### Failure Mode 1: Short Circuit

- **Cause:** Overvoltage, surge current, thermal runaway
- **Frequency:** 60% of power diode failures
- **Characteristics:**
  - Forward and reverse resistance 0.01–0.5 Ω
  - No rectification function
  - Package thermal capacity preserved
  - Rated for high current paths

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| High-Current Jumper | High | Original current rating maintained; 3–60A capacity |
| Current Shunt Resistor | High | Very low resistance; usable for high-current measurement with millivolt drop |
| Heat Spreader | Medium | TO-220/TO-247 packages designed for thermal management; 1–5W dissipation |
| Temperature Sensor | Medium | Residual junction properties; 2–5 mV/°C |

### Failure Mode 2: Open Circuit

- **Cause:** Bond wire fusing, metallization evaporation, lead fracture
- **Frequency:** 25% of failures
- **Characteristics:**
  - Infinite resistance both directions
  - Package and mechanical structure preserved
  - Thermal mass intact

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| High-Power Spacer | High | TO-220/TO-247 provides heatsink mounting; electrical isolation preserved |
| Thermal Mass Element | Medium | Large packages have significant heat capacity; thermal inertia for smoothing |
| Antenna Element | Low | Package leads shorter than signal diodes; limited RF utility |

### Failure Mode 3: Increased Forward Voltage

- **Cause:** Junction aging, thermal cycling, partial degradation
- **Frequency:** 15% of failures
- **Characteristics:**
  - Forward voltage 2–5× nominal
  - Still conducts but with higher loss
  - Temperature sensitivity increased

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Voltage Drop Element | Medium | Provides fixed voltage offset; crude voltage reference |
| Temperature Sensor | High | Enhanced thermal coefficient; 5–15 mV/°C sensitivity |
| Current Limiter (Crude) | Low | Higher forward drop limits current in series circuits |

---

## Environmental Interaction Matrix

| Condition | Observed Effect | Repurpose Impact | Notes |
|---|---|---|---|
| High Temperature | Forward voltage decreases; leakage ↑ | Better thermal sensor at elevated temps | Negative temperature coefficient |
| Surge Current | Junction degradation | Current shunt capability | Derate for reliability |
| High Humidity | Package corrosion | Minimal impact on shorted device | Sealed packages resistant |
| Thermal Cycling | Wire bond fatigue | Open circuit risk ↑ | Spacer application preserved |

---

## Testing Procedures

- **Forward Voltage:** Apply rated current; measure Vf; normal per datasheet; failure >2× nominal
- **Reverse Leakage:** Apply rated reverse voltage; measure leakage; normal <1 mA; failure = short circuit
- **Thermal Resistance:** Measure junction temp at known power; compare to datasheet θ_JC
