# Schottky Diode Repurposing Specifications (Stub)

## Overview
Fast-switching, low-forward-voltage diodes commonly used in rectifiers and RF applications.

---

## Common Failure Modes

### 1. Short Circuit
- **Cause**: Overvoltage, thermal overload  
- **Repurpose**: Low-value shunt resistor, crude current sense element

### 2. Open Circuit
- **Cause**: Bond wire break, metallization burnout  
- **Repurpose**: PCB spacer, antenna stub from intact leads

### 3. Leakage Increase
- **Cause**: Aging, temperature stress  
- **Repurpose**: Humidity/temperature proxy sensor (leakage as signal)

---

## Environmental Notes
- Leakage rises strongly with heat  
- Radiation or contamination accelerates failure, exploitable for sensing
