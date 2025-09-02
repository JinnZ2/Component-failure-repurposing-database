# Power Management IC Repurposing Specifications (Stub)

## Overview
Regulators, converters, and switching controllers.

---

## Common Failure Modes

### 1. Shorted Regulator
- **Cause**: Overvoltage, thermal runaway  
- **Repurpose**: Low-value resistor, thermal pad

### 2. Open Control Loop
- **Cause**: Feedback failure  
- **Repurpose**: Fixed voltage drop element

### 3. Drifted Reference
- **Cause**: Aging, temperature cycling  
- **Repurpose**: Environmental voltage sensor

---

## Environmental Notes
- Thermal variation alters reference voltage, usable for temp sensing
