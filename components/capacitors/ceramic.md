# Capacitor Repurposing Specifications — Ceramic

## Component Overview
**Type**: Ceramic Capacitor (NP0/X7R/Z5U)  
**Original Function**: Energy storage, decoupling, filtering  
**Package Types**: Through-hole discs, SMD 0603/0805  
**Typical Specs**: 1pF–100µF, 6.3–200V

## Failure Mode Analysis

### 1. Open Circuit (common)
- **Cause**: Lead fracture, dielectric crack  
- **Repurpose**: PCB spacer, parasitic capacitor (~0.1–2pF)

### 2. Value Drift
- **Cause**: Moisture absorption, dielectric aging  
- **Repurpose**: Humidity sensor (capacitance vs RH), low-accuracy timing element

### 3. Short Circuit
- **Cause**: Dielectric breakdown  
- **Repurpose**: Fused link (sacrificial protection), thermal mass for heat spreading

## Environmental Interaction
- **Humidity**: Increases leakage, usable for sensing  
- **Temperature**: Non-linear capacitance, exploitable for thermal sensing  

## Implementation Examples
- Failed ceramic → humidity sensor input  
- Failed ceramic → RF stub/decoupling element
