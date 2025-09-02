# SD Card Repurposing Specifications (Stub)

## Overview
Removable flash-based storage modules.

---

## Common Failure Modes

### 1. File System Corruption
- **Cause**: Power loss, wear-out  
- **Repurpose**: Raw block storage, append-only logging

### 2. Bad Blocks
- **Cause**: Wear, aging  
- **Repurpose**: Partial use as circular buffer, entropy source

---

## Environmental Notes
- Sensitive to vibration and shock  
- Heat accelerates wear-out
