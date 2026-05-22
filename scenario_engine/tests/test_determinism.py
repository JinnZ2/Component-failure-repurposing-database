"""Same (class, seed) ⇒ same ScenarioState at every tick."""

import unittest

from scenario_engine.scenarios.cascade_events import (
    SharedSubstrateFailure,
    SingleComponentThenPropagation,
    TimingDriftCascade,
)
from scenario_engine.scenarios.environmental_events import (
    EMInterference,
    HumidityIntrusion,
    RadiationBurst,
)
from scenario_engine.scenarios.mechanical_events import (
    FatigueCycling,
    ImpactShock,
    VibrationResonance,
)
from scenario_engine.scenarios.power_events import Brownout, GroundLoop, VoltageSag
from scenario_engine.scenarios.thermal_events import (
    AmbientDrift,
    HeatSpikeLocalized,
    ThermalRunawayCascade,
)


ALL_SCENARIOS = [
    HeatSpikeLocalized,
    AmbientDrift,
    ThermalRunawayCascade,
    VoltageSag,
    Brownout,
    GroundLoop,
    VibrationResonance,
    ImpactShock,
    FatigueCycling,
    SingleComponentThenPropagation,
    SharedSubstrateFailure,
    TimingDriftCascade,
    HumidityIntrusion,
    EMInterference,
    RadiationBurst,
]


class DeterminismTests(unittest.TestCase):
    def test_each_scenario_is_deterministic(self):
        for cls in ALL_SCENARIOS:
            with self.subTest(scenario=cls.__name__):
                a = cls(seed=7, max_ticks=40)
                b = cls(seed=7, max_ticks=40)
                states_a = [a.step().to_dict() for _ in range(40)]
                states_b = [b.step().to_dict() for _ in range(40)]
                self.assertEqual(states_a, states_b)

    def test_seed_changes_noise(self):
        # With nonzero noise, different seeds should give different sensor values.
        s0 = HeatSpikeLocalized(seed=0, max_ticks=10)
        s1 = HeatSpikeLocalized(seed=1, max_ticks=10)
        for _ in range(10):
            a = s0.step()
            b = s1.step()
            # Same tick & timestamp …
            self.assertEqual(a.tick, b.tick)
            # … but the noisy sensor values differ.
            va = a.sensors["thermal"]["Q1"]["value"]
            vb = b.sensors["thermal"]["Q1"]["value"]
            if va != vb:
                return
        self.fail("All readings identical across seeds — noise is not seeded.")


if __name__ == "__main__":
    unittest.main()
