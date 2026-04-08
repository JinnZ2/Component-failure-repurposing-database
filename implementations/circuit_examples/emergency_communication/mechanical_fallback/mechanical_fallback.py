"""
Mechanical fallback using vibration motor (TX) and accelerometer (RX).
Range: cm to meters via structure (table, wall, chassis).
"""

import RPi.GPIO as GPIO
import time
import threading
import math
from typing import Optional, Callable, Tuple

class MechanicalTransmitter:
    def __init__(self, motor_pin=12, pwm_freq=100):
        """
        motor_pin: GPIO pin controlling vibration motor (via transistor or motor driver)
        pwm_freq: PWM frequency for motor speed control
        """
        self.pin = motor_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.pin, pwm_freq)
        self.pwm.start(0)  # off

    def set_intensity(self, intensity: float):
        """Set vibration intensity (0.0 to 1.0)."""
        self.pwm.ChangeDutyCycle(intensity * 100)

    def send_bit(self, bit: int, duration_ms=200):
        """1 = vibrate at 100% intensity, 0 = off."""
        if bit:
            self.set_intensity(1.0)
        else:
            self.set_intensity(0.0)
        time.sleep(duration_ms / 1000.0)

    def send_morse_char(self, ch: str, wpm=20):
        """Send Morse code via vibrations (dot = short buzz, dash = long buzz)."""
        morse_map = {
            'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
            'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
            'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
            'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
            'Y': '-.--', 'Z': '--..', '0': '-----', '1': '.----', '2': '..---',
            '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...',
            '8': '---..', '9': '----.', ' ': ' '
        }
        code = morse_map.get(ch.upper(), '')
        dot_duration = 1.2 / wpm  # seconds
        dash_duration = 3 * dot_duration
        symbol_gap = dot_duration
        letter_gap = 3 * dot_duration
        for sym in code:
            if sym == '.':
                self.set_intensity(1.0)
                time.sleep(dot_duration)
                self.set_intensity(0.0)
                time.sleep(symbol_gap)
            elif sym == '-':
                self.set_intensity(1.0)
                time.sleep(dash_duration)
                self.set_intensity(0.0)
                time.sleep(symbol_gap)
            elif sym == ' ':
                time.sleep(letter_gap)

    def send_message(self, message: str, as_morse=True):
        """Send message as Morse code or raw OOK."""
        if as_morse:
            for ch in message:
                self.send_morse_char(ch)
                time.sleep(0.2)
        else:
            for ch in message:
                self.send_byte(ord(ch), duration_ms=100)

    def send_byte(self, byte: int, duration_ms=100):
        for bit in format(byte, '08b'):
            self.send_bit(int(bit), duration_ms)

    def cleanup(self):
        self.pwm.stop()
        GPIO.cleanup(self.pin)


class MechanicalReceiver:
    def __init__(self, i2c_bus=1, accel_type='mpu6050', threshold=0.2):
        """
        Uses accelerometer (MPU6050 or ADXL345) to detect vibrations.
        threshold: minimum magnitude change to consider as vibration.
        """
        self.threshold = threshold
        self.accel = None
        if accel_type == 'mpu6050':
            try:
                import board
                import adafruit_mpu6050
                i2c = board.I2C()
                self.accel = adafruit_mpu6050.MPU6050(i2c)
            except ImportError:
                print("Adafruit MPU6050 library not found. Using mock.")
        elif accel_type == 'adxl345':
            try:
                import adafruit_adxl34x
                import board
                i2c = board.I2C()
                self.accel = adafruit_adxl34x.ADXL345(i2c)
            except ImportError:
                print("ADXL345 library not found. Using mock.")
        else:
            self.accel = None

    def read_vibration_magnitude(self) -> float:
        """Return the magnitude of acceleration change (0-1 normalized)."""
        if self.accel:
            x, y, z = self.accel.acceleration
            # Simple magnitude
            mag = math.sqrt(x*x + y*y + z*z)
            # Normalize: assume max around 10 m/s² (~1g)
            return min(1.0, mag / 10.0)
        else:
            # Mock: random vibration
            import random
            return random.uniform(0, 0.3)

    def detect_vibration(self) -> bool:
        """Return True if vibration magnitude > threshold."""
        return self.read_vibration_magnitude() > self.threshold

    def receive_bit(self, timeout=1.0) -> Optional[int]:
        start = time.time()
        while time.time() - start < timeout:
            if self.detect_vibration():
                return 1
            time.sleep(0.02)
        return 0

    def receive_byte(self) -> Optional[int]:
        bits = []
        for _ in range(8):
            bit = self.receive_bit(timeout=0.3)
            bits.append(str(bit))
            time.sleep(0.05)
        return int(''.join(bits), 2) if len(bits) == 8 else None

    def receive_message(self, max_len=20) -> str:
        chars = []
        for _ in range(max_len):
            b = self.receive_byte()
            if b is None or b == 0:
                break
            chars.append(chr(b))
        return ''.join(chars)
