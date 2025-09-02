# Switching Transistor Repurposing Specifications (Stub)

## Overview
Small-signal transistors optimized for fast digital switching in logic circuits.

---

## Common Failure Modes

### 1. Open Junction
- **Cause**: Metallization fatigue, bond wire fracture  
- **Repurpose**: Spacer, antenna stub (lead length useful at HF/VHF)

### 2. Shorted Junction
- **Cause**: Overcurrent, electrostatic discharge  
- **Repurpose**: Low-value jumper, current shunt in non-critical paths

### 3. Gain Loss / Parameter Drift
- **Cause**: Aging, repeated switching stress  
- **Repurpose**: Noise source, environmental drift sensor (temp/humidity)

---

## Environmental Notes
- **Temperature**: Switching speed slows with heat, usable as thermal stress indicator  
- **Radiation**: Increases leakage, exploitable as a crude radiation sensor  

---

## Next Steps
- Populate with measured switching delay changes  
- Add examples of failed parts used as entropy sources in microcontrollers  
- Expand environmental response data (temperature, radiation, humidity)
