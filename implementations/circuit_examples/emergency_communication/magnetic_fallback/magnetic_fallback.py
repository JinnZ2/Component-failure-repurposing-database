"""
Magnetic fallback using transformer coupling.
Drive primary coil, sense secondary. Range: cm to tens of cm.
Works with degraded transformers or custom coils.
"""

import RPi.GPIO as GPIO
import time
import threading
from typing import Optional, Callable

class MagneticTransmitter:
    def __init__(self, drive_pin=12, carrier_freq_hz=1000, duty_cycle=50):
        """
        drive_pin: GPIO pin connected to primary coil (via transistor or H‑bridge)
        carrier_freq_hz: frequency of magnetic field (1kHz typical)
        """
        self.pin = drive_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.pin, carrier_freq_hz)
        self.pwm.start(0)  # off initially

    def send_bit(self, bit: int, duration_ms=10):
        """Send a single bit (1 = carrier on, 0 = off)."""
        if bit:
            self.pwm.ChangeDutyCycle(50)  # 50% duty cycle
        else:
            self.pwm.ChangeDutyCycle(0)
        time.sleep(duration_ms / 1000.0)

    def send_byte(self, byte: int, duration_ms=10):
        for bit in format(byte, '08b'):
            self.send_bit(int(bit), duration_ms)

    def send_message(self, message: str, baud=100):
        bit_duration = 1.0 / baud
        for ch in message:
            self.send_byte(ord(ch), bit_duration * 1000)
        self.send_bit(0, bit_duration*1000)  # stop

    def cleanup(self):
        self.pwm.stop()
        GPIO.cleanup(self.pin)


class MagneticReceiver:
    def __init__(self, sense_pin=0, adc_channel=0, threshold=0.5):
        """
        sense_pin: if using ADC via SPI/I2C, specify channel; else if using GPIO input with comparator.
        For simplicity, assume an MCP3008 ADC on SPI.
        """
        self.adc_channel = adc_channel
        self.threshold = threshold
        # Initialize ADC (example with Adafruit_MCP3008)
        try:
            import Adafruit_MCP3008
            self.adc = Adafruit_MCP3008.MCP3008(clk=18, cs=25, miso=23, mosi=24)
        except ImportError:
            print("MCP3008 library not found. Using mock ADC.")
            self.adc = None

    def read_signal(self) -> float:
        """Read induced voltage from secondary coil (0-1.0 normalized)."""
        if self.adc:
            raw = self.adc.read_adc(self.adc_channel)  # returns 0-1023
            return raw / 1023.0
        else:
            # Mock: return random value for simulation
            import random
            return random.uniform(0, 1)

    def detect_bit(self) -> int:
        """Return 1 if signal > threshold, else 0."""
        return 1 if self.read_signal() > self.threshold else 0

    def receive_byte(self, timeout=0.5) -> Optional[int]:
        start = time.time()
        bits = []
        while len(bits) < 8 and (time.time() - start) < timeout:
            bits.append(str(self.detect_bit()))
            time.sleep(0.01)  # bit sampling rate
        if len(bits) == 8:
            return int(''.join(bits), 2)
        return None

    def receive_message(self, max_len=50) -> str:
        chars = []
        for _ in range(max_len):
            b = self.receive_byte()
            if b is None or b == 0:
                break
            chars.append(chr(b))
        return ''.join(chars)
