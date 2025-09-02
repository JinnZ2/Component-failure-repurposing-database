# Microcontroller Repurposing Specifications (Stub)

## Overview
General-purpose ICs with CPU, memory, and peripherals (Arduino, PIC, STM32).

---

## Common Failure Modes

### 1. Flash Wear-Out
- **Cause**: Excessive reprogramming  
- **Repurpose**: Fixed-function controller (ROM firmware locked)

### 2. Peripheral Failure
- **Cause**: ESD, pin driver burnout  
- **Repurpose**: Use remaining GPIOs as signal routers or fixed pull-ups

### 3. CPU Lockup
- **Cause**: Radiation, aging, timing errors  
- **Repurpose**: Oscillator source (internal clock), watchdog-like timing element

---

## Environmental Notes
- Radiation induces bit flips → usable for radiation sensing  
- Heat accelerates timing instability
