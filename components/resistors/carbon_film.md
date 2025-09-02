# Carbon Film Resistor Repurposing Specifications (Stub)

## Overview
General-purpose resistors with carbon film on ceramic.

## Common Failure Modes
### 1) Open Circuit
- **Cause**: Overcurrent, film fracture
- **Repurpose**: PCB spacer; RF parasitic capacitor (~0.2–2 pF)

### 2) Value Drift
- **Cause**: Moisture, aging
- **Repurpose**: Humidity/temperature proxy (ppm/°C ↑), trend sensing

### 3) Short/Low Ohm Scar
- **Cause**: Film burn-through and lead bridge
- **Repurpose**: Jumper (≤1–3 A by lead gauge), crude shunt

## Environmental Notes
- RH ↑ → resistance drift accelerates (2–5×)
- Heat cycling → predictable drift curves (map for sensing)
