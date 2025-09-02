# Emergency RF Redundancy (Degraded-Hardware TX)

Goal: transmit basic telemetry/alerts even after multiple component failures by repurposing failed parts and simplifying modulation.

## Design Principles
- **ISM bands** only (region-legal): 433 MHz, 868/915 MHz, 2.4 GHz
- **Simple OOK/FSK** with minimal parts
- **Antenna from leftovers**: open/failed diodes/resistors as radiators
- **Entropy sources**: leaky diodes/BJTs for IDs or backoff timing
- **Tiered fallbacks**: full TX → low-power beacon → LF audio inductive

## Safety & Legal
- Observe local RF regulations: band, ERP limits, spurious emissions.
- Mark this as **non-critical** comms; not for life-critical signalling.

## Hardware Patterns
1) **LC Pierce/Colpitts** using partial-good caps + wire-wound as inductor  
2) **Shorted MOSFET/BJT as shunt** for OOK keying (low-Ω “switch”)  
3) **Antenna**: open diode/resistor leads cut to ~λ/4 or ~λ/8  
4) **Detector fallback**: LED/photodiode as crude RSSI indicator on receive rigs

## Fallback Ladder
- **Tier A**: MCU toggles OOK on LC at 433/915/2400 MHz  
- **Tier B**: If MCU GPIOs dead → 555-like RC oscillator keys LC (or use drifted thermistor network)  
- **Tier C**: No RF stable LC → audio LF via transformer/inductor coupling (wired or magnetic)

## Files
- `simple_ook_tx.md` – minimal OOK beacon with repurposed parts
- `antenna_repurpose.md` – turning failed parts into radiators
- `sdr_receive_notes.md` – how to verify with USB SDR
- `arduino_ook_beacon.ino` – example sketch (timing + GPIO key)
