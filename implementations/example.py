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
