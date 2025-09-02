# RF Fallback Communication (Stub)

## Concept
Repurpose degraded LC tanks, resistors, and diodes to sustain minimal RF signaling even after major failures.

## Modalities
- OOK beacon via shorted BJT/MOSFET
- Antennas from failed diode/resistor leads
- Noise-based entropy for backoff timing

## Characteristics
- Band: ISM only (433/868/915 MHz, 2.4 GHz)
- Bandwidth: bits per second to few kbps
- Range: 1–50 m depending on geometry and power
