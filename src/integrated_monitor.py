# integrated_monitor.py
import sys
import time
import random
from pathlib import Path

# Resolve sibling imports within src/
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from geometric_monitoring_engine import GeometricMonitoringSystem
from hardware_bridge_encoder import HardwareBridgeEncoder
from sensors.physical_sensor import PhysicalSensor

# Dummy sensor for demonstration
class SimulatedResistor(PhysicalSensor):
    def sample(self):
        # Simulate drift after 10 seconds
        t = time.time() - self.start_time
        if t < 10:
            v = 5.0 + random.uniform(-0.1, 0.1)
            mode = "none"
            health = 0.95
        else:
            v = 8.5 + random.uniform(-0.2, 0.2)
            mode = "drift"
            health = 0.4
        return {
            "type": "resistor",
            "mode": mode,
            "health_score": health,
            "drift_pct": abs(v-5.0)/5.0*100,
            "v": v,
            "i": v/1000.0,   # 1k ohm
            "t": 25.0,
            "salvageable": health < 0.5
        }
    def __init__(self):
        self.start_time = time.time()

# Main integration
if __name__ == "__main__":
    # Setup geometric monitoring
    geo_system = GeometricMonitoringSystem(cube_side=3)
    geo_system.start()

    # Setup sensor and encoder
    encoder = HardwareBridgeEncoder()
    resistor = SimulatedResistor()

    # Monitor loop — feed sensor samples into the geometric system
    try:
        for _ in range(300):   # 30 seconds at 0.1s interval
            sample = resistor.sample()
            # Feed raw reading to geometric monitoring
            geo_system.feed_sensor("R1", sample["v"], "V", sample["type"])
            # Also encode via hardware bridge for binary/token view
            geo = {
                "component_type": sample["type"],
                "failure_mode": sample["mode"],
                "health_score": sample["health_score"],
                "drift_pct": sample["drift_pct"],
                "voltage_v": sample["v"],
                "current_a": sample["i"],
                "temperature_c": sample["t"],
                "salvageable": sample["salvageable"],
            }
            encoder.from_geometry(geo)
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    geo_system.stop()
