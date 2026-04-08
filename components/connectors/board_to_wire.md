# Board-to-Wire Connectors — Failure & Repurposing Specification

**Status:** Stub  
**Validation Level:** Theoretical  
**Last Updated:** 2026-04-08

---

## Component Overview

```yaml
component_type: board_to_wire_connector
connector_style: socket/crimp
original_function: PCB-to-wire harness interconnection
types:
  - Molex KK series (2.54mm)
  - JST XH/PH series (2.0–2.5mm)
  - Dupont-style housings
  - Screw terminals
current_rating: 1–10A depending on type
voltage_rating: 250–600V
```

---

## Failure Mode Analysis

### Failure Mode 1: Crimp Degradation

- **Cause:** Vibration, thermal cycling, improper crimping
- **Frequency:** 40% of failures
- **Characteristics:**
  - Resistance increase at crimp junction
  - Intermittent connection under stress
  - Localized heating at crimp point

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Temperature Indicator | Medium | Localized heating at bad crimp detectable with thermal camera or thermistor |
| Vibration-Activated Switch | Medium | Intermittent connection correlates with vibration amplitude |
| Current Limiter (Crude) | Low | Increased resistance limits current; unreliable but usable in emergency |

### Failure Mode 2: Housing Fatigue / Latch Failure

- **Cause:** Repeated insertion/removal, UV exposure, mechanical stress
- **Frequency:** 35% of failures
- **Characteristics:**
  - Latch no longer holds connector in place
  - Pins may partially disengage
  - Housing cracks visible

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Strain Relief Anchor | Medium | Housing still provides mechanical strain relief even without latch |
| Wire Guide | High | Physical form factor maintained for wire routing |

### Failure Mode 3: Pin Corrosion / Oxidation

- **Cause:** Environmental exposure, dissimilar metals, humidity
- **Frequency:** 25% of failures
- **Characteristics:**
  - Contact resistance increases
  - Green/white corrosion products visible
  - Progressive from exposed areas inward

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Humidity Sensor | Medium | Corrosion resistance correlates with humidity; calibratable |
| Galvanic Cell (Crude) | Low | Dissimilar metal corrosion can produce small voltage; nanoamp-scale |

---

## Environmental Interaction Matrix

| Condition | Observed Effect | Repurpose Impact | Notes |
|---|---|---|---|
| High Humidity | Corrosion accelerates | Humidity sensing | Resistance-based detection |
| Vibration | Crimp loosening | Vibration indicator | Detectable via resistance spikes |
| Thermal Cycling | Housing fatigue | Mechanical stress tracker | Cumulative damage visible |
| Salt Spray | Rapid corrosion | Corrosion environment indicator | Coastal/marine applications |

---

## Testing Procedures

- **Pull Test:** Crimp retention force; normal >5N; failure <2N
- **Contact Resistance:** Normal <100 mΩ; failure >500 mΩ
- **Latch Test:** Manual engagement verification; should click and hold
