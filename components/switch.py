class SimulatedSwitch(PhysicalSensor):
    """Simulates a switch with increasing contact resistance or sticking."""
    def __init__(self, nominal_resistance_mohm=5.0, fail_resistance_mohm=100.0, drift_start=12.0):
        self.nominal = nominal_resistance_mohm
        self.fail = fail_resistance_mohm
        self.drift_start = drift_start
        self.start_time = time.time()

    def sample(self) -> dict:
        elapsed = time.time() - self.start_time
        if elapsed < self.drift_start:
            r = self.nominal + random.uniform(-0.5, 0.5)
            mode = "none"
        else:
            drift_factor = min(1.0, (elapsed - self.drift_start) / 15.0)
            r = self.nominal + drift_factor * (self.fail - self.nominal)
            r += random.uniform(-2, 2)
            mode = "high_resistance" if r > self.nominal * 5 else "oxidation"
        health = max(0.0, 1.0 - (r - self.nominal) / (self.fail - self.nominal)) if self.fail != self.nominal else 1.0
        drift_pct = (r - self.nominal) / self.nominal * 100 if self.nominal != 0 else 0
        v = r * 0.001  # 1mA
        return {
            "type": "switch",
            "mode": mode,
            "health_score": health,
            "drift_pct": drift_pct,
            "v": v,
            "i": 0.001,
            "t": 25.0,
            "salvageable": health < 0.5,
            "nominal": self.nominal,
            "fail_threshold": self.fail
        }
