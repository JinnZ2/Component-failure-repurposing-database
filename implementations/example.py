if __name__ == "__main__":
    system = GeometricMonitoringSystem(cube_side=3)
    system.start()

    # Simulate a resistor that fails after 10 seconds
    import numpy as np
    import time
    start = time.time()
    while time.time() - start < 30:
        t = time.time() - start
        if t < 10:
            v = 5.0 + np.random.normal(0, 0.1)
        else:
            v = 8.5 + np.random.normal(0, 0.2)  # drifted high
        system.feed_sensor("resistor_R1", v, "V", "resistor")
        system.run_self_diagnosis()
        time.sleep(0.1)

    system.stop()


def rf_ook_transmit(message: str, pin: int = 17):
    """Transmit OOK using a GPIO pin (Raspberry Pi or similar)."""
    # This is pseudo-code; adapt to your hardware
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT)
    for bit in message:
        if bit == '1':
            GPIO.output(pin, GPIO.HIGH)
        else:
            GPIO.output(pin, GPIO.LOW)
        time.sleep(0.001)


if __name__ == "__main__":
    system = GeometricMonitoringSystem(cube_side=3)
    system.start()

    # Simulate a resistor that drifts after 10 seconds
    start = time.time()
    while time.time() - start < 30:
        t = time.time() - start
        if t < 10:
            v = 5.0 + np.random.normal(0, 0.1)  # normal
        else:
            v = 8.5 + np.random.normal(0, 0.2)  # drifted high
        system.feed_sensor("resistor_R1", v, "V", "resistor")
        system.run_self_diagnosis()
        time.sleep(0.1)

    system.stop()
