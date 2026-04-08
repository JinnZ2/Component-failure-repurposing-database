import time
import random
from components.physical_sensor import PhysicalSensor


class SimulatedMotor(PhysicalSensor):
    """Simulates a DC motor with bearing wear (vibration) or winding short."""
    def __init__(self, nominal_current=0.5, fail_current=2.0, drift_start=18.0):
        self.nominal = nominal_current
        self.fail = fail_current
        self.drift_start = drift_start
        self.start_time = time.time()
        self.state = "operational"

    def sample(self) -> dict:
        elapsed = time.time() - self.start_time
        if elapsed < self.drift_start:
            i = self.nominal + random.uniform(-0.05, 0.05)
            mode = "none"
            vibration = 0.1 + random.uniform(0, 0.05)  # g
        else:
            drift_factor = min(1.0, (elapsed - self.drift_start) / 10.0)
            if self.state == "operational":
                self.state = random.choice(["winding_short", "bearing_wear"])
            if self.state == "winding_short":
                i = self.nominal + drift_factor * (self.fail - self.nominal)
                i += random.uniform(-0.1, 0.1)
                mode = "winding_short"
                vibration = 0.5 + random.uniform(0, 0.2)
            else:  # bearing_wear
                i = self.nominal + random.uniform(-0.1, 0.1)  # current may be normal
                mode = "bearing_wear"
                vibration = 1.0 + drift_factor * 5 + random.uniform(0, 0.5)
        health = max(0.0, 1.0 - (i - self.nominal) / (self.fail - self.nominal)) if self.fail != self.nominal else 1.0
        drift_pct = (i - self.nominal) / self.nominal * 100 if self.nominal != 0 else 0
        # Vibration is not directly in the geometry dict; we'll put it in 'extra' field
        return {
            "type": "motor",
            "mode": mode,
            "health_score": health,
            "drift_pct": drift_pct,
            "v": i * 12.0,  # assume 12V supply, voltage sensed
            "i": i,
            "t": 25.0 + drift_factor * 30,  # temperature rise
            "salvageable": health < 0.5,
            "nominal": self.nominal,
            "fail_threshold": self.fail,
            "vibration_g": vibration
        }
