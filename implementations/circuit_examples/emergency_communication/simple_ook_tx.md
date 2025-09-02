# Simple OOK TX with Repurposed Parts

## Target Bands
- 433.92 MHz (EU/ITU), 915 MHz (US), 2.4 GHz worldwide ISM — verify region.

## Core
- **Resonator**: wire-wound resistor as L + ceramic cap as C (even drifted)
- **Keying**: shorted MOSFET/BJT as shunt (on/off)
- **Drive**: MCU pin or RC astable if MCU degraded

## Build Steps
1. Form LC: start with L ~100–250 nH (wire-wound), C per band (calc below).
2. Connect LC to MCU pin via small series R (100–330 Ω).
3. Place failed-BJT/MOSFET across LC to ground; gate/base driven by MCU → OOK.
4. Antenna: open resistor/diode leads cut near quarter-wave; ground plane as counterpoise.
5. Power limit: keep output very low; verify on SDR/spectrum.

## Approx C for f0 = 1/(2π√(LC))
- 433 MHz, L=180 nH → C ≈ 1.6 pF
- 915 MHz, L=100 nH → C ≈ 0.30 pF
- 2.4 GHz, L=33 nH → C ≈ 0.13 pF
(Use ceramic/stray capacitance; trim by lead length)

## Notes
- Stability is poor but sufficient for short bursts/beacons.
- Add ID/backoff derived from diode/BJT noise → uniqueness under chaos.
