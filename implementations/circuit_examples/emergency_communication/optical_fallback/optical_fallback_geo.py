"""
Optical fallback communication using LED (TX) and photodiode (RX).
Works on Raspberry Pi with GPIO.
"""

import RPi.GPIO as GPIO
import time

class OpticalTransmitter:
    def __init__(self, led_pin=18, carrier_freq_hz=38000):  # 38kHz IR carrier (optional)
        self.led_pin = led_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(led_pin, GPIO.OUT)
        self.pwm = None
        if carrier_freq_hz:
            self.pwm = GPIO.PWM(led_pin, carrier_freq_hz)
            self.pwm.start(0)

    def send_bit(self, bit):
        if self.pwm:
            if bit == 1:
                self.pwm.ChangeDutyCycle(50)  # on
            else:
                self.pwm.ChangeDutyCycle(0)   # off
        else:
            GPIO.output(self.led_pin, bit)
        time.sleep(0.001)  # 1ms per bit

    def send_byte(self, byte):
        for bit in format(byte, '08b'):
            self.send_bit(int(bit))

    def send_message(self, message: str, baud=1000):
        bit_duration = 1.0 / baud
        for ch in message:
            self.send_byte(ord(ch))
            time.sleep(bit_duration)

    def blink_sos(self):
        """Simple SOS pattern without modulation."""
        pattern = [1,1,1,0,0,0,1,1,1]  # SOS
        for bit in pattern:
            GPIO.output(self.led_pin, bit)
            time.sleep(0.2)
        GPIO.output(self.led_pin, 0)

    def cleanup(self):
        if self.pwm:
            self.pwm.stop()
        GPIO.cleanup(self.led_pin)

class OpticalReceiver:
    def __init__(self, photodiode_pin=17):
        self.pin = photodiode_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN)

    def read_bit(self):
        return GPIO.input(self.pin)

    # More complex decoding would be needed; for demo, just print state
    def monitor(self, duration=5):
        start = time.time()
        while time.time() - start < duration:
            print(f"Light level: {self.read_bit()}")
            time.sleep(0.01)
