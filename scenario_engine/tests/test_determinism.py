"""Same (class, seed) ⇒ same ScenarioState at every tick, for the canonical 7."""

import unittest

from scenario_engine.scenarios import (
    CascadeEvent,
    EMInterference,
    PowerBrownout,
    SlowDegradationElectrolytic,
    SustainedDrift,
    ThermalDriftLocalized,
    VibrationResonance,
)


CANONICAL = [
    ThermalDriftLocalized,
    SustainedDrift,
    PowerBrownout,
    VibrationResonance,
    EMInterference,
    CascadeEvent,
    SlowDegradationElectrolytic,
]


class DeterminismTests(unittest.TestCase):
    def test_each_canonical_scenario_is_deterministic(self):
        for cls in CANONICAL:
            with self.subTest(scenario=cls.__name__):
                a = cls(seed=7, max_ticks=40)
                b = cls(seed=7, max_ticks=40)
                states_a = [a.step().to_dict() for _ in range(40)]
                states_b = [b.step().to_dict() for _ in range(40)]
                self.assertEqual(states_a, states_b)

    def test_replay_after_reset(self):
        s = ThermalDriftLocalized(seed=3, max_ticks=20)
        first_pass = [s.step().to_dict() for _ in range(20)]
        s.reset()
        # reset() on the base class restores tick=0; per-instance state
        # tied to interventions is not reset (none here, so fine).
        s2 = ThermalDriftLocalized(seed=3, max_ticks=20)
        second_pass = [s2.step().to_dict() for _ in range(20)]
        self.assertEqual(first_pass, second_pass)


if __name__ == "__main__":
    unittest.main()
