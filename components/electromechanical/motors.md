# Motors — Failure & Repurposing Specification

**Status:** Stub  
**Validation Level:** Literature Backed  
**Last Updated:** 2026-04-08

---

## Component Overview

```yaml
component_type: motor
original_function: Electromechanical energy conversion (electrical → rotational)
types:
  - DC brushed motor
  - DC brushless (BLDC)
  - Stepper motor
  - Servo motor
  - Vibration motor (ERM/LRA)
voltage_range: 1.5–48V typical
current_range: 10 mA–30A
speed_range: 100–30000 RPM
```

---

## Failure Mode Analysis

### Failure Mode 1: Brush Wear / Commutator Damage (Brushed DC)

- **Cause:** Mechanical wear, arcing, contamination
- **Frequency:** 40% of brushed motor failures
- **Characteristics:**
  - Increased electrical noise
  - Reduced torque
  - Intermittent operation
  - Commutator scoring visible

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Generator | High | Spin shaft manually or via wind/water; generates proportional voltage |
| Tachometer | High | Back-EMF proportional to RPM; effective speed sensor |
| Vibration Source | Medium | Unbalanced rotor or intermittent operation creates vibration |
| Noise Source | Medium | Brush arcing as entropy for random generation |

### Failure Mode 2: Winding Failure (Open/Short)

- **Cause:** Thermal overstress, insulation breakdown, mechanical damage
- **Frequency:** 30% of motor failures
- **Characteristics:**
  - Open: infinite resistance on affected winding
  - Short: reduced resistance, excessive current draw
  - Partial: intermittent or reduced performance

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Inductor / Choke (Open Winding) | Medium | Remaining intact windings usable for filtering; inductance in mH range |
| Heating Element (Shorted Winding) | Medium | Resistive heating from shorted turns; low-power thermal applications |
| Electromagnetic Actuator | Medium | Energize intact winding(s) for magnetic field generation |
| Mechanical Bearing Assembly | High | Shaft and bearings preserved for mechanical applications |

### Failure Mode 3: Bearing Failure

- **Cause:** Wear, contamination, overload, misalignment
- **Frequency:** 20% of motor failures
- **Characteristics:**
  - Increased friction and noise
  - Shaft wobble
  - Electrical function may be preserved

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Low-Speed Generator | Medium | Still generates voltage at reduced efficiency; suitable for wind/water |
| Static Electromagnet | High | Energize windings without rotation for magnetic field generation |
| Vibration Sensor | Low | Bearing roughness creates vibration signature; detectable pattern |

### Failure Mode 4: Demagnetization (Permanent Magnet Motors)

- **Cause:** Excessive current, high temperature, physical shock
- **Frequency:** 10% of failures
- **Characteristics:**
  - Reduced torque and back-EMF
  - Lower no-load speed
  - Magnets still partially magnetized

#### Repurposing Applications

| Application | Effectiveness | Notes |
|---|---|---|
| Weak Magnetic Source | Medium | Partial magnetization still useful for reed switch actuation |
| Low-Torque Generator | Low | Reduced but measurable voltage output |
| Magnetic Proximity Sensor | Medium | Detectable field at close range; proximity switch via reed relay |

---

## Environmental Interaction Matrix

| Condition | Observed Effect | Repurpose Impact | Notes |
|---|---|---|---|
| High Temperature | Insulation degrades; magnets weaken | Generator output decreases; heating element improves | Derate above 80°C |
| High Humidity | Bearing corrosion; insulation absorption | Reduced life but sensing still viable | Seal bearings |
| Vibration | Bearing wear accelerates | Vibration signature analysis | Detectable pattern change |
| Dust / Contamination | Brush wear accelerates; bearing contamination | Noise source quality improves | More random arcing |

---

## Testing Procedures

- **Winding Resistance:** DMM across terminals; compare to datasheet ±15%
- **Insulation Resistance:** 500V megohmmeter; winding to case; normal >100 MΩ
- **Free Spin Test:** Spin by hand; should be smooth; rough = bearing failure
- **Back-EMF Test:** Spin at known RPM; measure voltage; proportional to magnet strength
- **No-Load Current:** Apply rated voltage; excessive current indicates friction or shorts
