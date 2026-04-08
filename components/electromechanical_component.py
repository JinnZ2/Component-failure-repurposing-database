import time
import random
from components.physical_sensor import PhysicalSensor


class SimulatedRelay(PhysicalSensor):
    """Simulates a relay with contact welding or coil failure."""
    def __init__(self, nominal_coil_resistance=100.0, fail_time=20.0):
        self.nominal_coil = nominal_coil_resistance
        self.fail_time = fail_time
        self.start_time = time.time()
        self.state = "operational"  # operational, welded, coil_open

    def sample(self) -> dict:
        elapsed = time.time() - self.start_time
        if elapsed < self.fail_time:
            mode = "none"
            coil_res = self.nominal_coil + random.uniform(-5, 5)
            contact_res = 0.01 + random.uniform(0, 0.01)  # ohms
            health = 1.0
        else:
            # After fail_time, randomly choose failure mode
            if self.state == "operational":
                self.state = random.choice(["welded", "coil_open"])
            if self.state == "welded":
                mode = "contact_welding"
                coil_res = self.nominal_coil + random.uniform(-10, 10)
                contact_res = 0.0  # shorted
                health = 0.3
            else:  # coil_open
                mode = "coil_failure"
                coil_res = 1e6  # open circuit
                contact_res = 0.1  # may still be switchable manually
                health = 0.2
        # Convert to pseudo-voltage (1mA sense)
        v_coil = coil_res * 0.001
        v_contact = contact_res * 0.001
        return {
            "type": "relay",
            "mode": mode,
            "health_score": health,
            "drift_pct": 0,
            "v": v_coil,          # main sensing is coil resistance
            "i": 0.001,
            "t": 25.0,
            "salvageable": health < 0.5,
            "nominal": self.nominal_coil,
            "fail_threshold": 1e6 if self.state == "coil_open" else 0.0,
            "contact_resistance": contact_res
        }
