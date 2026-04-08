# integrated_monitor.py
import time
import random
from geometric_monitoring import GeometricMonitoringSystem
from generic_hardware_interface import GenericHardwareInterface, PhysicalSensor

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

    # Setup hardware interface with encoder (already inside geo_system)
    hw_interface = GenericHardwareInterface(encoder=geo_system.encoder)
    resistor = SimulatedResistor()
    hw_interface.register_sensor("R1", resistor)

    # Monitor loop
    try:
        for _ in range(300):   # 30 seconds
            state = hw_interface.get_system_state()
            for comp_id, info in state.items():
                # The state dict already contains binary, hex, status
                # But we also want to feed geometry for cube detection
                # We need to rebuild geometry from info? Better: let hardware interface push directly.
                # For simplicity, we call feed_geometry with the raw sample data.
                # But get_system_state already computed health/drift – we can reuse.
                # We'll just feed the geometry we already have in the loop.
                # Actually, we should modify get_system_state to return the geometry dict.
                # For now, we manually feed.
                pass
            # Simpler: just feed sensor samples directly
            geo_system.feed_geometry("R1", resistor.sample())
            time.sleep(0.1)
    except KeyboardInterrupt:
        geo_system.stop()
