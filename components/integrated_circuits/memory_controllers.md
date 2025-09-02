# Memory Controller Repurposing Specifications (Stub)

## Overview
ICs that handle RAM/cache access and refresh cycles.

---

## Common Failure Modes

### 1. Address Line Failure
- **Cause**: Bond wire or logic failure  
- **Repurpose**: Reduced memory space, address remapping

### 2. Timing Drift
- **Cause**: Aging, temperature stress  
- **Repurpose**: Variable delay element, crude timing generator

---

## Environmental Notes
- Heat alters refresh cycles, exploitable for delay-based sensing  
- Radiation accelerates errors
