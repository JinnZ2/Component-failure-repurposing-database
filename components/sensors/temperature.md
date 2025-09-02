# Temperature Sensor Repurposing Specifications (Stub)

## Overview
Sensors that convert thermal changes into electrical signals (thermistors, RTDs, IC-based).

---

## Common Failure Modes

### 1. Open Circuit
- **Cause**: Lead fracture, thermal overstress  
- **Repurpose**: Mechanical spacer, parasitic capacitance element

### 2. Value Drift
- **Cause**: Aging, repeated cycling  
- **Repurpose**: Relative temperature trend sensor (not absolute)

### 3. Increased Noise
- **Cause**: Junction degradation  
- **Repurpose**: Entropy source for random generation

---

## Environmental Notes
- Heat accelerates drift but still usable as trend monitor  
- Mechanical stress alters response, exploitable for dual sensing (temp + stress)
