# Edge Connectors — Failure & Repurposing Specification

**Status:** Stub  
**Validation Level:** Literature Backed  
**Last Updated:** 2026-04-08

---

## Component Overview

```yaml
component_type: edge_connector
connector_style: edge
original_function: PCB edge-to-slot interconnection (PCI, ISA, card edge)
contact_material: Gold-plated copper alloy
pitch: 1.27–2.54mm
current_rating: 1–2A per contact
voltage_rating: 100–250V
mating_cycles: 50–200 rated
```

---

## Failure Mode Analysis

### Failure Mode 1: Contact Oxidation / Tarnish

- **Cause:** Atmospheric exposure, sulfur compounds, humidity
- **Frequency:** 45% of edge connector failures
- **Characteristics:**
  - Surface resistance increases 10–100×
  - Visible discoloration on gold-plated contacts
  - Non-uniform degradation across contact fingers

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Air Quality Sensor | Medium | Oxidation rate correlates with atmospheric contaminants; sulfur detection possible |
| Humidity Monitor | Medium | Tarnish rate varies with humidity; cumulative exposure indicator |
| Contact Resistance Standard | Low | Degraded contacts provide known high-resistance reference points |

### Failure Mode 2: Mechanical Misalignment / Bent Contacts

- **Cause:** Improper insertion, vibration, thermal expansion
- **Frequency:** 30% of failures
- **Characteristics:**
  - Partial or no contact on affected pins
  - Visible deformation of contact fingers
  - Remaining contacts may still function

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Reduced-Channel Interface | Medium | Use remaining good contacts for lower-bandwidth communication |
| Spring Contact | Low | Deformed contacts can serve as crude spring-loaded switches |
| Mechanical Key | High | Physical alignment maintained; prevents wrong-card insertion |

### Failure Mode 3: Fretting Corrosion

- **Cause:** Micro-motion from vibration under load
- **Frequency:** 25% of failures
- **Characteristics:**
  - Oxide debris between contacts
  - Intermittent high-resistance events
  - Worse under vibration, better when static

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Vibration Detector | Medium | Resistance spikes correlate with vibration events |
| Environmental Stress Logger | Medium | Fretting rate tracks cumulative mechanical stress |

---

## Environmental Interaction Matrix

| Condition | Observed Effect | Repurpose Impact | Notes |
|---|---|---|---|
| Sulfur Atmosphere | Accelerated tarnish | Air quality correlation | Industrial environments |
| High Humidity | Oxidation rate increases | Better humidity indicator | 50–95% RH sensitivity |
| Vibration | Fretting corrosion | Vibration detection | Threshold depends on contact force |
| Thermal Cycling | Differential expansion | Intermittent contact | Thermal stress history |

---

## Testing Procedures

- **Contact Resistance:** Four-wire measurement; normal <20 mΩ; failure >100 mΩ
- **Insertion Force:** Measure with force gauge; normal 1–5N per contact
- **Visual Inspection:** Magnification for oxidation patterns, debris, deformation
