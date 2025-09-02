# Flash Memory Repurposing Specifications (Stub)

## Overview
NAND/NOR flash memory used for non-volatile data storage.

---

## Common Failure Modes

### 1. Stuck Bits
- **Cause**: Wear-out, charge leakage  
- **Repurpose**: ROM with fixed data (firmware stub, lookup tables)

### 2. Endurance Limit
- **Cause**: Too many program/erase cycles  
- **Repurpose**: Append-only logging, entropy source from read errors

---

## Environmental Notes
- Radiation ↑ bit errors → usable for radiation sensing  
- Heat accelerates charge loss
