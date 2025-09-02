# Inductor Repurposing Specifications — Ferrite Core

## Component Overview
**Type**: Ferrite Core Inductor  
**Original Function**: Energy storage in magnetic field, filtering  
**Package Types**: Axial, toroidal, SMD shielded  
**Typical Specs**: 1µH–10mH, 0.1–10A

## Failure Mode Analysis

### 1. Open Winding
- **Cause**: Wire break, solder joint failure  
- **Repurpose**: Ferrite core as EMI absorber, mechanical spacer

### 2. Core Saturation / Damage
- **Cause**: Overcurrent, physical crack  
- **Repurpose**: Partial transformer core, thermal sink

### 3. Resistance Increase
- **Cause**: Aging, corrosion, partial shorts  
- **Repurpose**: Heating element (low-power), crude resistive load

## Environmental Interaction
- **Vibration**: Core fracture can add piezoelectric-like response  
- **Humidity**: Increases corrosion, alters winding resistance  

## Implementation Examples
- Cracked ferrite used as EMI choke  
- Failed winding coil reconfigured as low-frequency antenna
