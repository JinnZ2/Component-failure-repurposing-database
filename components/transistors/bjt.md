# Transistor Repurposing Specifications — BJT

## Component Overview
**Type**: Bipolar Junction Transistor (NPN/PNP)  
**Original Function**: Amplification, switching  
**Package Types**: TO-92, TO-220, SOT-23  
**Typical Specs**: 20–100V, 100mA–10A

## Failure Mode Analysis

### 1. Collector-Emitter Short
- **Cause**: Overcurrent, thermal runaway  
- **Repurpose**: Low-value resistor (0.05–1Ω), PCB jumper, thermal sensor (junction drop vs T)

### 2. Open Junction
- **Cause**: Bond wire break, metallization loss  
- **Repurpose**: Mechanical spacer, antenna stub (leads as RF element)

### 3. Gain Degradation
- **Cause**: Aging, radiation, thermal stress  
- **Repurpose**: Noise source (base leakage), weak amplifier for entropy generation

## Environmental Interaction
- **Radiation**: Leakage increase, exploitable for radiation sensing  
- **Heat**: hFE drift → temperature sensor

## Implementation Examples
- Dead BJT array as distributed temperature sensors  
- Shorted BJT as part of a crude shunt resistor bank
