"""
Thermal fallback using a resistor (TX) and thermistor (RX).
Bandwidth: ~1-10 bits per minute.
Range: cm (direct contact) or tens of cm (radiant).
"""

import time
import threading
import math
from typing import Optional

try:
    import RPi.GPIO as GPIO
except ImportError:
    class _MockGPIO:
        BCM = OUT = IN = 0
        def setmode(self, *a): pass
        def setup(self, *a, **kw): pass
        def output(self, *a): pass
        def input(self, *a): return 0
        def cleanup(self, *a): pass
        def PWM(self, pin, freq):
            return type('PWM', (), {
                'start': lambda s, d: None,
                'stop': lambda s: None,
                'ChangeDutyCycle': lambda s, d: None,
            })()
    GPIO = _MockGPIO()

class ThermalTransmitter:
    def __init__(self, resistor_pin=18, power_percent=100):
        """
        resistor_pin: GPIO pin driving a transistor that powers a resistor (or a failed component)
        power_percent: 0-100, how hard to drive (100% = full heat)
        """
        self.pin = resistor_pin
        self.power = min(100, max(0, power_percent))
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        # Use PWM to control heat intensity (optional, simple on/off is fine)
        self.pwm = GPIO.PWM(self.pin, 100)  # 100Hz
        self.pwm.start(0)

    def set_heat(self, on: bool):
        """Turn heater on or off."""
        if on:
            self.pwm.ChangeDutyCycle(self.power)
        else:
            self.pwm.ChangeDutyCycle(0)

    def send_bit(self, bit: int, duration_sec=6):
        """
        Send a single bit.
        1 = heat on for duration_sec, 0 = off for duration_sec.
        Typical bit rate: 10 bits per minute (6 sec/bit).
        """
        self.set_heat(bit == 1)
        time.sleep(duration_sec)
        self.set_heat(False)

    def send_byte(self, byte: int, bit_duration_sec=6):
        for bit in format(byte, '08b'):
            self.send_bit(int(bit), bit_duration_sec)

    def send_message(self, message: str, bit_duration_sec=6):
        """
        Send a string as ASCII bytes.
        Very slow but works as a beacon.
        """
        for ch in message:
            self.send_byte(ord(ch), bit_duration_sec)
            # Extra pause between characters
            time.sleep(bit_duration_sec)

    def send_heartbeat(self, on_duration=2, off_duration=10):
        """Simple 'I'm alive' beacon: short heat pulse, long pause."""
        while True:
            self.set_heat(True)
            time.sleep(on_duration)
            self.set_heat(False)
            time.sleep(off_duration)

    def cleanup(self):
        self.pwm.stop()
        GPIO.cleanup(self.pin)


class ThermalReceiver:
    def __init__(self, thermistor_pin=0, adc_channel=0, threshold=0.3, sampling_interval=1.0):
        """
        thermistor_pin: if using ADC, specify channel; else if using GPIO comparator.
        threshold: normalized temperature rise (0-1) to consider a bit=1.
        sampling_interval: how often to read (seconds).
        """
        self.threshold = threshold
        self.sampling_interval = sampling_interval
        self.last_temp = None
        # Initialize ADC (e.g., MCP3008)
        try:
            import Adafruit_MCP3008
            self.adc = Adafruit_MCP3008.MCP3008(clk=18, cs=25, miso=23, mosi=24)
        except ImportError:
            print("MCP3008 not found. Using mock ADC.")
            self.adc = None

    def read_temperature(self) -> float:
        """Return normalized temperature (0-1) from thermistor via ADC."""
        if self.adc:
            raw = self.adc.read_adc(0)  # channel 0
            # Convert to temperature (simplified: raw 0-1023 -> 0-100°C)
            temp = (raw / 1023.0) * 100.0
            # Normalize to 0-1 (assume 20-80°C range)
            norm = max(0.0, min(1.0, (temp - 20.0) / 60.0))
            return norm
        else:
            # Mock: simulate slow temperature drift
            import random
            return random.uniform(0.2, 0.4)

    def detect_heat_pulse(self, timeout_sec=30) -> bool:
        """
        Wait for a sustained temperature rise above threshold.
        Returns True if heat detected within timeout.
        """
        start = time.time()
        while time.time() - start < timeout_sec:
            temp = self.read_temperature()
            if temp > self.threshold:
                return True
            time.sleep(self.sampling_interval)
        return False

    def receive_bit(self, bit_duration_sec=6, timeout_sec=30) -> Optional[int]:
        """
        Determine if a bit (1 = heat) or (0 = no heat) is being sent.
        Assumes sender toggles heat for exactly bit_duration_sec.
        """
        # Sample before and after the expected window
        # For simplicity, we'll just check for presence of heat
        # This is very crude; better would be to sync with clock.
        if self.detect_heat_pulse(timeout_sec):
            # Wait for heat to possibly drop (if bit=1 would turn off after duration)
            time.sleep(bit_duration_sec)
            if not self.detect_heat_pulse(bit_duration_sec):
                return 1  # heat was present then went away
            else:
                # Heat remained – maybe noise or still on? Assume 0
                return 0
        else:
            return 0

    def receive_byte(self, bit_duration_sec=6) -> Optional[int]:
        bits = []
        for _ in range(8):
            bit = self.receive_bit(bit_duration_sec)
            if bit is None:
                return None
            bits.append(str(bit))
            time.sleep(bit_duration_sec)  # gap between bits
        return int(''.join(bits), 2)

    def receive_message(self, max_len=10, bit_duration_sec=6) -> str:
        chars = []
        for _ in range(max_len):
            b = self.receive_byte(bit_duration_sec)
            if b is None or b == 0:
                break
            chars.append(chr(b))
            time.sleep(bit_duration_sec * 2)  # gap between chars
        return ''.join(chars)
