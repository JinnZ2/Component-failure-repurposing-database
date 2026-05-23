"""scenario_engine — substrate self-awareness calibration playground.

Plug-in module for `Component-failure-repurposing-database`. Python stdlib only.

Public surface:

  from scenario_engine.scenarios.base import (
      Scenario, ScenarioState, SensorReading, ComponentState,
  )
  from scenario_engine.runner import ScenarioRunner
  from scenario_engine.claims import ClaimWriter, ClaimRejected
  from scenario_engine.validators import OutcomeChecker, Verdict

  from scenario_engine.scenarios.thermal_events import (
      HeatSpikeLocalized, AmbientDrift, ThermalRunawayCascade,
  )
  from scenario_engine.scenarios.power_events import (
      VoltageSag, Brownout, GroundLoop,
  )
  from scenario_engine.scenarios.mechanical_events import (
      VibrationResonance, ImpactShock, FatigueCycling,
  )
  from scenario_engine.scenarios.cascade_events import (
      SingleComponentThenPropagation, SharedSubstrateFailure, TimingDriftCascade,
  )
  from scenario_engine.scenarios.environmental_events import (
      HumidityIntrusion, EMInterference, RadiationBurst,
  )
"""
