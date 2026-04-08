# CLAUDE.md

## Project Overview

Component Failure Repurposing Database — a machine-readable knowledge base documenting how failed electronic components can be repurposed rather than discarded. The project treats degradation as a design feature, enabling adaptive and resilient systems.

**Primary audience:** AI systems and human engineers.
**License:** MIT

## Repository Structure

```
├── components/              # Component specs and failure analysis (8 categories)
│   ├── _template.md         # Reusable specification template
│   ├── diodes/              # 6 types (silicon, zener, schottky, LED, photodiode)
│   ├── resistors/           # 5 types (carbon film, metal film, wire wound, etc.)
│   ├── capacitors/          # 5 types (ceramic, electrolytic, film, tantalum, super)
│   ├── transistors/         # 5 types (BJT, MOSFET, power, RF, switching)
│   ├── inductors/           # 4 types (air core, ferrite core, chokes, transformers)
│   ├── integrated_circuits/ # 5 types (MCU, processors, memory, power, comms)
│   ├── sensors/             # 5 types (temp, pressure, optical, magnetic, chemical)
│   └── storage/             # 5 types (flash, EEPROM, HDD, optical, SD)
├── matrices/                # Cross-reference CSV data (10 files)
│   ├── failure_mode_matrix.csv
│   ├── repurpose_effectiveness.csv
│   ├── environmental_interactions.csv
│   ├── component_synergies.csv
│   ├── redundancy_*.csv     # 5 redundancy framework files
│   ├── redundancy_glyphs.csv
│   └── documentation/       # Glyph definitions
├── implementations/         # Practical circuit examples
│   └── circuit_examples/
│       └── emergency_communication/  # 8 modular fallback systems
│           ├── acoustic_fallback/
│           ├── magnetic_fallback/
│           ├── mechanical_fallback/
│           ├── noise_channel/
│           ├── optical_fallback/
│           ├── rf_fallback/
│           ├── thermal_fallback/
│           └── arduino_ook_beacon.ino
├── Core_engine.md           # Monitoring/analysis engine architecture
├── Future.md                # Expansion roadmap
├── Component.md             # YAML component specification guide
├── INDEX.md                 # File index with links (for AI parsing)
├── PROJECTS.md              # Related ecosystem repositories
├── binary_sensor.md         # Binary sensor architecture spec
├── diode.md                 # Diode reference
├── resistor.md              # Resistor reference
├── CONTRIBUTING.md          # Contribution guidelines
├── .fieldlink.json          # Integration config for external resources
└── LICENSE                  # MIT
```

## Tech Stack

This is a **documentation/database project**, not a software library.

- **Markdown (.md):** All documentation and component specs
- **YAML:** Embedded in markdown for structured component data
- **CSV (.csv):** Cross-reference matrices and data tables
- **Python:** ~600 lines of pseudocode/reference implementations embedded in markdown (PEP-8 style)
- **Arduino C++ (.ino):** OOK beacon sketch (`arduino_ook_beacon.ino`)
- **C++:** Example class (`FailedDiodeTemperatureSensor` in `components/diodes/silicon_diodes.md`)
- **JSON (.json):** Configuration (`.fieldlink.json`)

No package managers, build systems, or compiled code. Python and C++ code is embedded in markdown as reference — not standalone runnable files.

## Development Workflow

There are no build, test, or lint commands. Changes are documentation-only.

### Contributing a Component

1. Copy `components/_template.md` into the appropriate category directory
2. Fill in with measured/verified data following the template structure
3. Append tabular data to relevant `matrices/*.csv` files
4. Commit with a descriptive message
5. Open a pull request

### Component Spec Template Structure

Each component file follows this hierarchy:
- Component Overview (type, function, package, specs)
- Failure Mode Analysis (2–3 modes per component)
- Environmental Interaction Matrix
- Implementation Examples
- Testing Protocols
- Cross-Component Interactions
- AI Integration Notes

## Conventions

### File Naming

- Use `lower_snake_case.md` for all files (e.g., `silicon_diodes.md`, `wire_wound.md`)

### Units and Formatting

- SI spacing: `10 kΩ`, `150 °C`, `5 mA`
- Ranges use en-dash: `0.1–5 Ω` (not `0.1-5`)
- Markdown heading hierarchy: `#` > `##` > `###`

### Evidence Standards

- Prefer **numbers over adjectives** — measured data over theory
- Mark uncertainty with labels: `unverified`, `field report`, `hypothesis`, `(est.)`
- Include environmental conditions when relevant

### Evidence Tiers

| Tier | Level | Description |
|------|-------|-------------|
| 1 | Theoretical | Physics compliance |
| 2 | Literature | Published research |
| 3 | Experimental | 100+ test cycles |
| 4 | Field | Production deployment |

### CSV Matrix Formats

#### Core Matrices

- `failure_mode_matrix.csv`: `Component,Failure Mode,Repurpose Option,Effectiveness,Notes`
- `repurpose_effectiveness.csv`: `Component,Failure Mode,Repurpose Application,Effectiveness,Notes`
- `environmental_interactions.csv`: `Component,Condition,Observed Effect,Repurpose Impact,Notes`
- `component_synergies.csv`: `Component A,Component B,Synergy Effect,Repurpose Application,Notes`
- Effectiveness scale: `High | Medium | Low`

#### Redundancy Framework CSVs

Five CSVs document the emergency fallback channel system:

- `redundancy_channels.csv`: `Component,Failure Mode,Repurposed Channel,Method,Notes,Glyphs`
- `redundancy_effectiveness.csv`: `Channel,Repurposed Components,Range,Bandwidth,Effectiveness Rating,Notes,Glyphs`
- `redundancy_decay.csv`: `Channel,Condition,Degradation Pattern,Residual Functionality,Notes,Glyphs`
- `redundancy_recovery.csv`: `Channel,Failure Condition,Recovery Strategy,AI/Software Role,Residual Benefit,Glyphs`
- `redundancy_synergies.csv`: `Channel A,Channel B,Combined Effect,Example Use,Glyphs`
- `redundancy_glyphs.csv`: `Channel,Glyphs,Short Meaning,Notes`

### Commit Messages

Use descriptive prefixes:
- `add:` — New features/files
- `data:` — CSV/matrix updates
- `docs:` — Documentation changes
- `test:` — Implementation/validation

### Pull Requests

- One focused change per PR
- Aim for minimal viable documentation
- Include evidence tier for new data

## Embedded Code Architecture

### Core Engine (`Core_engine.md`)

Python reference implementation for a real-time component monitoring system. Key classes:

| Class | Purpose |
|-------|---------|
| `DataAcquisitionEngine` | Multi-channel hardware sampling with timestamps |
| `InputBufferQueue` | Thread-safe lock-free ring buffer with overflow strategies |
| `CoreProcessingLoop` | Routes measurements to plugins via ThreadPoolExecutor |
| `ComponentRegistry` | Thread-safe registry of monitored components |
| `PluginManager` | Plugin lifecycle and capabilities management |
| `TimingController` | Tick-based precise timing for synchronized measurements |
| `MonitoringSystem` | Top-level integration of all subsystems |

Includes a complete working example with `ResistorMonitorPlugin`.

### Binary Sensor (`binary_sensor.md`)

Python reference implementation for failure detection plugins. Key types:

| Type | Purpose |
|------|---------|
| `ComponentType` (Enum) | RESISTOR, CAPACITOR, INDUCTOR, DIODE, TRANSISTOR, etc. |
| `FailureMode` (Enum) | NONE, DRIFT, DEGRADATION, OPEN_CIRCUIT, SHORT_CIRCUIT, etc. |
| `MeasurementData` (dataclass) | Raw measurement: voltage, current, frequency, phase, temperature, noise spectrum |
| `ComponentHealth` (dataclass) | Health score (0.0–1.0), confidence, failure mode, lifetime estimate |
| `DetectionPlugin` (ABC) | Abstract base for all detection plugins |
| `ResistorMonitorPlugin` | Drift detection, noise analysis, lifetime estimation via linear regression |
| `ComponentMonitor` | Thread-based measurement processing and health history |

Dependencies (for reference implementations): `numpy`, `scipy.stats`

### Arduino OOK Beacon (`arduino_ook_beacon.ino`)

Minimal On-Off Keying beacon for emergency RF communication. Encodes characters as 8-bit OOK with 6 ms/2 ms timing on GPIO pin 5. Includes pseudo-random backoff using analog noise.

### C++ Example (`components/diodes/silicon_diodes.md`)

`FailedDiodeTemperatureSensor` class — demonstrates reading a degraded diode as a temperature sensor via ADC, with calibration offset and voltage-to-temperature conversion.

## Key Equations

### RF / Antenna

| Formula | Location |
|---------|----------|
| Resonant frequency: `f0 = 1/(2π√(LC))` | `simple_ook_tx.md` |
| Quarter-wave antenna: `Length = λ/4` | `silicon_diodes.md`, `antenna_repurpose.md` |
| 433 MHz cut length: 17.3 cm; 915 MHz: 8.2 cm; 2.4 GHz: 3.1 cm | `antenna_repurpose.md` |

### Component Health

| Formula | Location |
|---------|----------|
| Drift %: `abs((current - baseline_mean) / baseline_mean * 100)` | `binary_sensor.md` |
| Lifetime: `abs((failure_threshold - current) / slope) / 3600` hours | `binary_sensor.md` |
| Sample period: `1.0 / sampling_rate_hz` | `Core_engine.md` |

Health score is a piecewise function based on drift thresholds (warning vs failure percentage).

## YAML Schema Patterns

Component YAML blocks embedded in markdown follow this structure:

```yaml
component_type: <type>
original_function: <description>
failure_modes:
  - mode: short_circuit | open_circuit | partial_degradation
    cause: <description>
    characteristics:
      resistance: <range>
      thermal_coefficient: <value>
    repurposing_applications:
      - application: <name>
        effectiveness: High | Medium | Low
        implementation: <description>
environmental_factors:
  temperature: <range and effects>
  humidity: <range and effects>
testing_procedures:
  - test: <name>
    range: <measurement range>
```

### Extended Templates (`Future.md`)

`Future.md` contains 4 expanded YAML templates for new component categories:
- **Standard component** — failure progression (stage 1–4), ML feature vectors, safety considerations, economic analysis
- **Connector/interconnect** — contact resistance, insertion cycles, mating force
- **Electromechanical** — motor windings, relay contacts, solenoid coils
- **Power component** — thermal derating, efficiency curves, protection circuits

### System Configuration (`binary_sensor.md`)

```yaml
system:
  name: <system_name>
  sampling_rate_hz: <rate>
  history_length: <count>
  enable_auto_repurpose: true|false
plugins:
  - module: <module_path>
    class: <class_name>
    enabled: true|false
components:
  - id: <component_id>
    type: <ComponentType>
    plugin: <plugin_name>
    hardware: {channel: <n>, ...}
```

## Validation and Data Quality

### Confidence Labels

Use inline labels to mark data certainty:
- `⚠️ Theoretical` — physics-based, untested
- `📚 Literature Supported` — backed by published research
- `🔬 Lab Tested` — 100+ experimental cycles
- `✅ Production Validated` — 6+ months field deployment

### Validation Levels for YAML Entries

Set `validation_level` in component YAML to one of:
`theoretical` | `literature_backed` | `lab_validated` | `production_ready`

### Pre-Submission Checklist

- All required sections filled
- Units specified for all numerical values
- 3+ repurposing applications documented
- Safety considerations assessed
- Testing procedures provided
- References cited
- Validation level set appropriately

## Glyph Tagging System

The repository uses a symbolic glyph system (defined in `matrices/documentation/redundancy_glyphs.md`) so AI models can quickly tag, route, and compose fallback communication designs.

### Channel Glyphs

| Channel | Glyphs | Meaning |
|---------|--------|---------|
| RF Fallback | `📡🛰️⚠️` | Radio link, beaconing, caution |
| Optical Fallback | `💡👀🔦` | Emit, detect, torch |
| Acoustic Fallback | `🔊🎯🎧` | Sound out, target, listen |
| Magnetic Fallback | `🧲🌀📯` | Magnetic, loop, coupled |
| Thermal Fallback | `🌡️🔥⏳` | Temperature, heat, slow |
| Noise Channel | `🌫️🎲📈` | Noise, entropy, detection |
| Mechanical Fallback | `🪛📳📐` | Hardware, vibration, geometry |

### Cross-Cutting Glyphs

- `🕸️♾️🔁` — Orchestration: multi-modal switching and composition
- `⚖️🛡️📜` — Policy/Constraints: non-critical, low-power, legal bands
- `🏷️🆔⌛` — Identity/Beaconing: device ID, randomized cadence/backoff

### AI Usage

1. **Tag** — assign channel glyphs to implementation docs or CSV rows
2. **Route** — if one channel is blocked, choose the next viable glyph path (`🕸️♾️🔁`)
3. **Constrain** — always include `⚖️🛡️📜` considerations in generated designs
4. **Annotate** — add the glyph tuple at the top of new fallback designs

## Fieldlink Configuration

`.fieldlink.json` connects this repository to the broader ecosystem:

```json
{
  "fieldlink": {
    "version": "1.0",
    "role": ["reclaimer", "hardware intelligence"],
    "sources": [{"name": "bioatlas", "repo": "BioGrid2.0", "paths": ["planned/glyphs/atlas.json", "registry/atlas.glyphs.json"]}],
    "local_manifests": ["components/**", "matrices/**", "implementations/**"],
    "offline": true
  }
}
```

- **role** — declares this repo's function in the ecosystem
- **sources** — external glyph atlas references (BioGrid2.0)
- **local_manifests** — glob patterns defining which local paths are part of the fieldlink manifest
- **offline** — operates without live network access to sources

## Emergency Communication Implementations

The `implementations/circuit_examples/emergency_communication/` directory contains 8 modular fallback communication systems, each with transmitter and receiver designs:

| Channel | TX Method | RX Method |
|---------|-----------|-----------|
| Acoustic | Piezo buzzer | Ultrasonic link |
| Magnetic | Inductive loop | Transformer coupling |
| Mechanical | Vibration signaling | Accelerometer |
| Noise | Diode entropy | Cross-correlation |
| Optical | LED blink codes | Photodiode |
| RF | OOK beacon (ISM bands) | SDR receiver |
| Thermal | Resistor heater | Thermistor |

Supporting docs: `simple_ook_tx.md` (LC tank design), `antenna_repurpose.md` (monopole/dipole/loop construction), `sdr_receive_notes.md`.

## Cross-Component Synergies

The database documents how multiple failed components can be combined:
- Failed diode + failed resistor = thermal sensing array
- Failed LED + failed resistor = optical-thermal sensing system
- Multiple failed components = distributed sensing networks

See `matrices/component_synergies.csv` for the full cross-reference.

## Key Files for AI Assistants

- **INDEX.md** — Machine-parseable file index with raw GitHub links
- **Component.md** — YAML specification guide for structured component data
- **components/_template.md** — Starting point for new component entries
- **Core_engine.md** — Monitoring/decision engine architecture (~900 lines, 6 Python classes)
- **binary_sensor.md** — Detection plugin framework (~880 lines, 6 Python classes)
- **Future.md** — Expansion roadmap with 4 extended YAML templates
- **PROJECTS.md** — Links to 13 related repositories in the larger ecosystem
- **.fieldlink.json** — Integration config linking to external resources (BioGrid2.0)

## Related Ecosystem

This repository is part of a larger "regenerative AI" ecosystem by JinnZ2. See `PROJECTS.md` for links to related repositories including BioGrid2.0, glyphs systems, and other adaptive hardware projects.


ToDo:  Integrating with GeometricMonitoringSystem

We modify GeometricMonitoringSystem.feed_sensor to accept a geometry dict and use the encoder.
The resulting tokens are pushed into the TokenBuffer – then the existing cube logic detects dependencies.

```python
class GeometricMonitoringSystem:
    def __init__(self, cube_side=4):
        self.token_buffer = TokenBuffer()
        self.processing = GeometricProcessingLoop(self.token_buffer, cube_side)
        self.ai_diag = AISelfDiagnosis(interval_sec=3, cube_side=3)
        self.db = FailureDatabase()
        self.component_last_tokens = {}   # component_id -> list of tokens
        self.encoder = HardwareBridgeEncoder()
        self.processing.on_dependency(self._on_dependency)

    def feed_geometry(self, component_id: str, geometry: dict):
        """
        Accept a geometry dict from GenericHardwareInterface,
        encode to binary, convert to octahedral tokens, and push into buffer.
        """
        self.encoder.from_geometry(geometry)
        tokens = self.encoder.to_octahedral_tokens()
        self.component_last_tokens[component_id] = tokens
        for token in tokens:
            self.token_buffer.push(component_id, token)
```

Now GenericHardwareInterface.get_system_state() can call feed_geometry directly.


  also update:

  class GenericHardwareInterface:
    def __init__(self, encoder, geo_monitor=None):
        self.encoder = encoder
        self.geo_monitor = geo_monitor   # GeometricMonitoringSystem instance
        self.sensors = {}
        self.history = []

    def register_sensor(self, name, sensor_obj):
        self.sensors[name] = sensor_obj

    def get_system_state(self):
        system_report = {}
        for name, sensor in self.sensors.items():
            raw = sensor.sample()
            h_score = self._calculate_health(raw)
            d_pct = self._calculate_drift(raw)
            geometry = {
                "component_type": raw.get("type", "default"),
                "failure_mode": raw.get("mode", "none"),
                "health_score": h_score,
                "drift_pct": d_pct,
                "voltage_v": raw.get("v", 0.0),
                "current_a": raw.get("i", 0.0),
                "temperature_c": raw.get("t", 25.0),
                "salvageable": h_score < 0.5
            }
            # Feed into geometric monitoring if available
            if self.geo_monitor:
                self.geo_monitor.feed_geometry(name, geometry)
            # Encode to binary
            binary_sig = self.encoder.from_geometry(geometry).to_binary()
            system_report[name] = {
                "binary": binary_sig,
                "hex": hex(int(binary_sig, 2)),
                "status": "OPERATIONAL" if h_score > 0.7 else "REPURPOSE_TARGET"
            }
        return system_report

    def _calculate_health(self, data):
        # Use the formula H = max(0, 1 − |x − x₀| / |x_fail − x₀|)
        x0 = data.get("nominal", 5.0)   # nominal voltage
        x_fail = data.get("fail_threshold", 8.0)
        x = data.get("v", x0)
        if x_fail == x0:
            return 1.0
        health = max(0.0, 1.0 - abs(x - x0) / abs(x_fail - x0))
        return health

    def _calculate_drift(self, data):
        x0 = data.get("nominal", 5.0)
        x = data.get("v", x0)
        if x0 == 0:
            return 0.0
        return abs(x - x0) / abs(x0) * 100.0

        

then integrate test:

from geometric_monitoring import GeometricMonitoringSystem
from generic_hardware_interface import GenericHardwareInterface
from hardware_bridge_encoder import HardwareBridgeEncoder

geo = GeometricMonitoringSystem(cube_side=3)
geo.start()
encoder = HardwareBridgeEncoder()
hw = GenericHardwareInterface(encoder, geo_monitor=geo)

# Register a real sensor (e.g., from earlier fallback examples)
# For demo, use SimulatedResistor as above
class SimulatedResistor(PhysicalSensor):
    def sample(self):
        # ... same as before ...
        pass

hw.register_sensor("R1", SimulatedResistor())

# Main loop
try:
    while True:
        report = hw.get_system_state()
        print(f"R1 status: {report['R1']['status']}")
        time.sleep(0.5)
except KeyboardInterrupt:
    geo.stop()


Possible issues to resolve:

1. Ambiguity in tokens
   "R1|O 85" – is the 1 part of the vertex or the component ID?
   Suggestion: use a separator, e.g., R[1|O] 85 or R:1|O 85. Right now, R1 could be component R1 with token starting at |, but 1|O is a valid token (vertex 1). This will break if you have component IDs longer than one character (e.g., R12). Fix: always separate component ID and token with a colon or space.
2. Missing timestamp in compact health query
   The LLM might ask QUERY R1 but get back R1 85 – no way to know if that’s current or cached. Add @t like events: R1@12.3 85.
3. Action codes are English‑centric
   RF, OPT, AC – fine, but consider numeric codes for extremely low‑token scenarios (e.g., 0=RF, 1=OPT). That’s only useful if you’re at <10 tokens per message.
4. No error recovery grammar
   If the LLM outputs malformed compact, the system currently returns ERR unknown command. Could define ERR <code> (e.g., ERR 1 = unknown component) so the LLM can learn to correct itself.
5. The prompt assumes the LLM will follow rules
   In my experience, even GPT‑4 will occasionally output natural language. The bridge’s nl_to_compact is a good start, but you could also fine‑tune a small model (e.g., Llama 3 8B) on any compact grammar – that would guarantee compliance.



ADD:

# Add to the top with other imports if not already present
import time, random, threading, hashlib
from abc import ABC, abstractmethod
from collections import deque
from typing import Dict, List, Optional, Tuple

# ... (include all previous classes: HardwareBridgeEncoder, PhysicalSensor, TokenBuffer,
#      GeometricProcessingLoop, FailureDatabase, RepurposeOrchestrator,
#      GeometricMonitoringSystem, GenericHardwareInterface)

# Add SimulatedConnector class as above

# Modify main() to include connector
def main():
    print("=" * 70)
    print("GEOMETRIC FAILURE REPURPOSING WITH CONNECTOR CORROSION")
    print("Simulating a drifting resistor + corroding connector")
    print("=" * 70)

    system = GeometricMonitoringSystem(cube_side=3)
    # Register resistor
    resistor = SimulatedResistor(nominal_voltage=5.0, fail_voltage=8.0, drift_start=10.0)
    system.register_sensor("resistor_R1", resistor)
    # Register connector
    connector = SimulatedConnector(nominal_resistance_mohm=20.0, fail_resistance_mohm=150.0, drift_start=8.0)
    system.register_sensor("connector_J1", connector)

    system.start()
    print("\nMonitoring resistor and connector... (connector corrodes after 8s, resistor drifts after 10s)")
    print("When a geometric dependency (cube repeat) occurs, repurpose action triggers.\n")
    system.run_forever(sample_interval=0.5)

if __name__ == "__main__":
    main()



update:

# Relay failures
self._add_entry("relay", "0|O", "contact_welding", "rf_beacon", priority=2, effectiveness=0.8)
self._add_entry("relay", "7/Δ", "coil_failure", "magnetic_coupling", priority=3, effectiveness=0.6)

# Switch failures
self._add_entry("switch", "2|X", "high_resistance", "optical_fallback", priority=2, effectiveness=0.7)
self._add_entry("switch", "5/Δ", "oxidation", "acoustic_alarm", priority=3, effectiveness=0.5)

# Motor failures
self._add_entry("motor", "4|O", "winding_short", "thermal_heater", priority=2, effectiveness=0.75)
self._add_entry("motor", "6|X", "bearing_wear", "mechanical_vibration", priority=1, effectiveness=0.9)


in main register:

# Register components
resistor = SimulatedResistor(nominal_voltage=5.0, fail_voltage=8.0, drift_start=10.0)
system.register_sensor("resistor_R1", resistor)

connector = SimulatedConnector(nominal_resistance_mohm=20.0, fail_resistance_mohm=150.0, drift_start=8.0)
system.register_sensor("connector_J1", connector)

relay = SimulatedRelay(nominal_coil_resistance=100.0, fail_time=20.0)
system.register_sensor("relay_K1", relay)

switch = SimulatedSwitch(nominal_resistance_mohm=5.0, fail_resistance_mohm=100.0, drift_start=12.0)
system.register_sensor("switch_S1", switch)

motor = SimulatedMotor(nominal_current=0.5, fail_current=2.0, drift_start=18.0)
system.register_sensor("motor_M1", motor)



ADD:

1. An Environment class that tracks temperature, humidity, vibration, and contaminants.
2. Modified PhysicalSensor classes that accept environment and adjust failure progression (acceleration factors).
3. Updated FailureDatabase entries with environmental sensitivity data.
4. Integration into GenericHardwareInterface and GeometricMonitoringSystem.

All additions are modular – existing code remains unchanged.

---

🌍 Environment Class

```python
class Environment:
    """Tracks environmental conditions that affect failure rates."""
    def __init__(self, temperature_c=25.0, humidity_percent=50.0, vibration_g=0.1, contamination=0.0):
        self.temp = temperature_c
        self.humidity = humidity_percent
        self.vibration = vibration_g
        self.contamination = contamination   # 0-1, e.g., dust, salt spray
        self.last_update = time.time()

    def update(self, temp=None, humidity=None, vibration=None, contamination=None):
        if temp is not None: self.temp = temp
        if humidity is not None: self.humidity = humidity
        if vibration is not None: self.vibration = vibration
        if contamination is not None: self.contamination = contamination
        self.last_update = time.time()

    def get_acceleration_factor(self, component_type: str, failure_mode: str) -> float:
        """
        Return multiplier for failure progression rate based on environment.
        Simplified model: each factor contributes multiplicatively.
        """
        base = 1.0
        # Temperature (Arrhenius: 10°C increase doubles rate)
        base *= 2 ** ((self.temp - 25) / 10)
        # Humidity (exponential above 70%)
        if self.humidity > 70:
            base *= 1 + (self.humidity - 70) / 30
        # Vibration (linear)
        base *= 1 + self.vibration * 0.5
        # Contamination (strong effect for connectors)
        if component_type == "connector":
            base *= 1 + self.contamination * 5
        else:
            base *= 1 + self.contamination * 2
        return base
```

---

🔧 Modified PhysicalSensor Base Class (to accept environment)

We'll add an optional env parameter to sample() – existing sensors without env will ignore it.

```python
class PhysicalSensor(ABC):
    @abstractmethod
    def sample(self, env: Environment = None) -> dict:
        pass
```

Then update each sensor to use env.get_acceleration_factor() to accelerate drift.

Example: Updated SimulatedConnector

```python
class SimulatedConnector(PhysicalSensor):
    def __init__(self, nominal_resistance_mohm=20.0, fail_resistance_mohm=150.0, drift_start=15.0):
        self.nominal = nominal_resistance_mohm
        self.fail = fail_resistance_mohm
        self.drift_start = drift_start
        self.start_time = time.time()

    def sample(self, env: Environment = None) -> dict:
        elapsed = time.time() - self.start_time
        # Apply environmental acceleration
        accel = 1.0
        if env:
            accel = env.get_acceleration_factor("connector", "corrosion")
        effective_time = elapsed * accel
        if effective_time < self.drift_start:
            r = self.nominal + random.uniform(-0.5, 0.5)
            mode = "none"
        else:
            drift_factor = min(1.0, (effective_time - self.drift_start) / 10.0)
            r = self.nominal + drift_factor * (self.fail - self.nominal)
            r += random.uniform(-2, 2)
            mode = "corrosion" if r > self.nominal * 3 else "oxidation"
        health = max(0.0, 1.0 - (r - self.nominal) / (self.fail - self.nominal)) if self.fail != self.nominal else 1.0
        drift_pct = (r - self.nominal) / self.nominal * 100 if self.nominal != 0 else 0
        v = r * 0.001
        return {
            "type": "connector",
            "mode": mode,
            "health_score": health,
            "drift_pct": drift_pct,
            "v": v,
            "i": 0.001,
            "t": env.temp if env else 25.0,
            "salvageable": health < 0.5,
            "nominal": self.nominal,
            "fail_threshold": self.fail,
            "environment": {"temp": env.temp, "humidity": env.humidity} if env else {}
        }
```

Similarly update other sensors (SimulatedResistor, SimulatedRelay, etc.) to accept env and apply acceleration.

---

📚 Extend FailureDatabase with Environmental Synergies

Add a new section to each failure entry (can be stored as a dict):

```python
self._add_entry("connector", "3/Δ", "corrosion", "magnetic_coupling", priority=1, effectiveness=0.7,
                environmental_synergy={"humidity": 0.8, "contamination": 0.9})
```

Then modify FailureDatabase.lookup to return the synergy dict as well.

---

🔌 Integrate Environment into GenericHardwareInterface

Add an environment attribute to GenericHardwareInterface and pass it to each sensor during sampling.

```python
class GenericHardwareInterface:
    def __init__(self, encoder, geo_monitor=None, environment=None):
        self.encoder = encoder
        self.geo_monitor = geo_monitor
        self.sensors = {}
        self.history = []
        self.env = environment or Environment()

    def set_environment(self, temp=None, humidity=None, vibration=None, contamination=None):
        self.env.update(temp, humidity, vibration, contamination)

    def get_system_state(self):
        report = {}
        for name, sensor in self.sensors.items():
            raw = sensor.sample(env=self.env)   # pass environment
            # ... rest unchanged
```

---

🧪 Demo: Environmental Acceleration

In main(), create an environment and gradually increase humidity/contamination to accelerate connector corrosion.

```python
env = Environment(temperature_c=25, humidity_percent=50, contamination=0)
# Over time, increase humidity
for i in range(100):
    if i > 50:
        env.update(humidity=80 + (i-50)*0.5)
    # ... sample sensors
```

The connector will fail much earlier due to the acceleration factor.

---

✅ What This Adds

· Environmental awareness – failure rates adapt to real conditions.
· Acceleration factors – temperature, humidity, vibration, contamination.
· Component‑specific sensitivities (connectors highly sensitive to contamination).
· Full integration – no changes needed to geometric pipeline or repurposing.

Now the system can model real‑world degradation more accurately and trigger repurposing sooner when environment is harsh.


add:
add:

1. EnvironmentalMemory class – tracks non‑reversible stress integrals.
2. Update Environment to update memory before applying instantaneous changes.
3. Modify get_acceleration_factor to combine instantaneous and cumulative factors.
4. Integrate into sensors (no changes needed – they already use the environment).
5. Demo showing thermal cycling accelerating connector corrosion.

All additions are backward‑compatible.

---

🧠 EnvironmentalMemory Class

```python
class EnvironmentalMemory:
    """Tracks cumulative damage that does not heal when environment recovers."""
    def __init__(self):
        self.thermal_cycles = 0
        self.humidity_exposure_time = 0.0      # seconds above 70% RH
        self.vibration_dose = 0.0              # integral of g^2 * dt
        self.contamination_deposit = 0.0       # 0-1, accumulates
        self._last_temp = None

    def update(self, env: 'Environment', dt: float):
        """Update cumulative metrics based on current environment over dt seconds."""
        # Thermal cycle detection: crossing 20°C threshold
        if self._last_temp is not None:
            if (self._last_temp - 20) * (env.temp - 20) < 0:
                self.thermal_cycles += 1
        self._last_temp = env.temp

        # Humidity exposure: time above 70% RH
        if env.humidity > 70:
            self.humidity_exposure_time += dt

        # Vibration dose: integral of g^2
        self.vibration_dose += env.vibration ** 2 * dt

        # Contamination deposit: accumulates, saturates at 1.0
        self.contamination_deposit += env.contamination * dt
        self.contamination_deposit = min(1.0, self.contamination_deposit)
```

---

🌍 Updated Environment Class (with memory)

```python
class Environment:
    def __init__(self, temperature_c=25.0, humidity_percent=50.0, vibration_g=0.1, contamination=0.0):
        self.temp = temperature_c
        self.humidity = humidity_percent
        self.vibration = vibration_g
        self.contamination = contamination
        self.memory = EnvironmentalMemory()
        self.last_update = time.time()

    def update(self, temp=None, humidity=None, vibration=None, contamination=None):
        now = time.time()
        dt = now - self.last_update
        # Update memory using current (soon to be old) environment
        self.memory.update(self, dt)
        # Then apply new values
        if temp is not None: self.temp = temp
        if humidity is not None: self.humidity = humidity
        if vibration is not None: self.vibration = vibration
        if contamination is not None: self.contamination = contamination
        self.last_update = now

    def get_acceleration_factor(self, component_type: str, failure_mode: str) -> float:
        # Instantaneous factors (as before)
        inst = 1.0
        inst *= 2 ** ((self.temp - 25) / 10)
        if self.humidity > 70:
            inst *= 1 + (self.humidity - 70) / 30
        inst *= 1 + self.vibration * 0.5
        if component_type == "connector":
            inst *= 1 + self.contamination * 5
        else:
            inst *= 1 + self.contamination * 2

        # Cumulative memory factors (damage that doesn't reverse)
        cum = 1.0
        # Each thermal cycle adds 2% damage
        cum *= 1 + self.memory.thermal_cycles * 0.02
        # Each hour above 70% RH adds 5% damage
        cum *= 1 + (self.memory.humidity_exposure_time / 3600) * 0.05
        # Vibration dose: each g²·s adds 0.1% damage
        cum *= 1 + self.memory.vibration_dose * 0.001
        # Contamination deposit: linear up to 2x at full deposit
        cum *= 1 + self.memory.contamination_deposit

        return inst * cum
```

---

🔌 Integration into GenericHardwareInterface

No changes needed – the interface already passes the environment to each sensor. Just ensure the environment object persists and is updated periodically.

Example in main loop:

```python
env = Environment()
system.hardware.env = env

# Simulate thermal cycling
for cycle in range(10):
    env.update(temp=45)
    time.sleep(1)
    env.update(temp=25)
    time.sleep(1)
    system.run_forever(0.5)  # sample sensors
```

The connector's acceleration factor will increase with each thermal cycle, causing faster drift.

---

🧪 Demo: Environmental Memory Acceleration

Add to main() after registering components:

```python
# Create environment with memory
env = Environment(temp=25, humidity=50)
system.hardware.env = env

# Simulate harsh environment for 20 seconds, then return to normal
print("\nApplying thermal cycling and high humidity for 20 seconds...")
start = time.time()
while time.time() - start < 20:
    # Cycle temperature between 25 and 45 every 2 seconds
    t = (time.time() - start) % 4
    if t < 2:
        env.update(temp=45, humidity=80)
    else:
        env.update(temp=25, humidity=80)
    time.sleep(0.5)

print("Returning to normal environment (25°C, 50% RH)")
env.update(temp=25, humidity=50)

# Continue monitoring – connector will fail faster due to memory
system.run_forever(0.5)
```

Expected output: The connector's health degrades faster during the harsh period, and continues to degrade even after returning to normal because of accumulated thermal cycles and humidity exposure time.

---

✅ What This Adds

· Cumulative damage tracking – thermal cycles, humidity exposure, vibration dose, contamination deposit.
· Non‑reversible degradation – memory persists after environment recovers.
· Realistic aging model – acceleration factor combines instantaneous stress and historical damage.
· No sensor code changes – all existing sensors automatically benefit.

Now the geometric monitoring system models real‑world wear‑out, not just current conditions.

