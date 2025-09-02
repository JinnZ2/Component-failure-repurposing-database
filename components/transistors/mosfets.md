# MOSFET Repurposing Specifications

## Component Overview
**Type**: MOSFET (N-channel / P-channel)  
**Original Function**: Power switching, amplification, logic control  
**Package Types**: TO-220, TO-247, SOT-23, QFN  
**Typical Specifications**: 20–100V, 1–100A, Rds(on) 1mΩ–500mΩ

---

## Failure Mode Analysis

### 1. Drain-Source Short (60–70% of failures)
**Cause**: Overvoltage, avalanche breakdown, thermal runaway  
**Characteristics**:
- Resistance: 0.01–0.1Ω  
- Gate often destroyed  
- Package intact with good thermal capacity  

**Repurposing Applications**:
- **Low-value Resistor**: Use shorted MOSFET as a shunt resistor  
- **Thermal Pad**: Package serves as small heat spreader  
- **Current Sensor**: Monitor voltage drop for ampere-range sensing  

---

### 2. Open Circuit Failure (20–25%)
**Cause**: Bond wire break, gate oxide rupture, metallization fracture  
**Characteristics**:
- Infinite resistance between terminals  
- Package still intact mechanically  
- Gate capacitance altered  

**Repurposing Applications**:
- **Mechanical Spacer**: Preserves PCB structure  
- **Antenna Stub**: Leads usable as RF element  
- **Capacitive Element**: Gate capacitance (10–1000pF) usable for timing  

---

### 3. Parameter Drift (5–10%)
**Cause**: Aging, hot-carrier injection, radiation exposure  
**Characteristics**:
- Threshold voltage shift (±20–50%)  
- Leakage current ↑  
- Noise generation ↑  

**Repurposing Applications**:
- **Voltage Sensor**: Use threshold drift as environmental proxy  
- **Noise Source**: Entropy for RNG  
- **Radiation Monitor**: Leakage scaling with dose  

---

## Environmental Interaction Matrix

|Condition|Observed Change|Repurpose Impact|
|---------|---------------|----------------|
|High Temp|Rds(on) ↑      |More useful as thermal sensor|
|High Humidity|Gate leakage ↑|Humidity detection possible|
|Radiation|Threshold shift |Environmental sensing|

---

## Implementation Examples

### Example 1: Emergency Current Monitor
- **Scenario**: MOSFET fails short in PSU  
- **Repurposing**: Use device as low-ohm shunt, measure voltage drop  
- **Benefits**: Minimal circuit redesign, continued monitoring  

### Example 2: RF Communication Backup
- **Scenario**: MOSFET fails open in driver stage  
- **Repurposing**: Leads cut/tuned as RF stub antenna  
- **Benefits**: Emergency comms restored without extra parts  

---

## Testing Protocols

  1.	Measure drain-source resistance
	2.	Check gate capacitance with LCR meter
	3.	Thermal test under load for heat sinking ability

    ---

## AI Integration Notes
- Record **threshold drift vs environment** for predictive models  
- Capture **failure distributions** to train classifiers  
- Tag **repurpose effectiveness** for shunt, sensor, RNG use cases
