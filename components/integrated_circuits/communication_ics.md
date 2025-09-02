# Communication IC Repurposing Specifications (Stub)

## Overview
Chips for UART, SPI, I2C, wireless modules, and transceivers.

---

## Common Failure Modes

### 1. Transmitter Burnout
- **Cause**: Overcurrent, ESD  
- **Repurpose**: Receiver-only mode, noise detector

### 2. Frequency Drift
- **Cause**: Aging, temperature  
- **Repurpose**: Crude RF oscillator, drift sensor

### 3. Protocol Logic Failure
- **Cause**: Radiation, timing error  
- **Repurpose**: Partial repeater, logic entropy source

---

## Environmental Notes
- Heat and radiation affect oscillator stability → useful as sensing element
