"""
Example: Simulate a degrading resistor with the Geometric Monitoring System.
"""
import sys
import time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from geometric_monitoring_engine import GeometricMonitoringSystem


def rf_ook_transmit(message: str, pin: int = 17):
    """Transmit OOK using a GPIO pin (Raspberry Pi or similar)."""
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        print(f"  [sim] RF OOK TX pin={pin}: {message}")
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT)
    for bit in message:
        GPIO.output(pin, GPIO.HIGH if bit == '1' else GPIO.LOW)
        time.sleep(0.001)
    GPIO.cleanup(pin)


if __name__ == "__main__":
    system = GeometricMonitoringSystem(cube_side=3)
    system.start()

    # Simulate a resistor that drifts after 10 seconds
    start = time.time()
    while time.time() - start < 30:
        t = time.time() - start
        if t < 10:
            v = 5.0 + np.random.normal(0, 0.1)   # normal
        else:
            v = 8.5 + np.random.normal(0, 0.2)    # drifted high
        system.feed_sensor("resistor_R1", v, "V", "resistor")
        system.run_self_diagnosis()
        time.sleep(0.1)

    system.stop()
