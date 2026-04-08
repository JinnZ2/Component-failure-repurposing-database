"""
Acoustic fallback using piezo buzzer / disk.
Modes:
- audible: 1-5 kHz, range 1-20 m (human detectable)
- ultrasonic: 40 kHz, range 0.1-3 m (requires receiver with envelope detection)
"""

import RPi.GPIO as GPIO
import time
import threading
import math
from typing import Optional, Callable

class AcousticTransmitter:
    def __init__(self, piezo_pin=13, mode='audible'):
        """
        piezo_pin: GPIO pin connected to piezo (via transistor or directly)
        mode: 'audible' (1-5kHz) or 'ultrasonic' (40kHz)
        """
        self.pin = piezo_pin
        self.mode = mode
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        self.freq = 2000 if mode == 'audible' else 40000
        self.pwm = GPIO.PWM(self.pin, self.freq)
        self.pwm.start(0)

    def tone_on(self):
        self.pwm.ChangeDutyCycle(50)

    def tone_off(self):
        self.pwm.ChangeDutyCycle(0)

    def send_bit(self, bit: int, duration_ms=50):
        """1 = tone on, 0 = tone off."""
        if bit:
            self.tone_on()
        else:
            self.tone_off()
        time.sleep(duration_ms / 1000.0)

    def send_morse_char(self, ch: str, wpm=20):
        """Send a single character in Morse code (simple mapping)."""
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
                self.tone_on()
                time.sleep(dot_duration)
                self.tone_off()
                time.sleep(symbol_gap)
            elif sym == '-':
                self.tone_on()
                time.sleep(dash_duration)
                self.tone_off()
                time.sleep(symbol_gap)
            elif sym == ' ':
                time.sleep(letter_gap)

    def send_message(self, message: str, as_morse=True):
        """Send a string via Morse code or raw OOK."""
        if as_morse:
            for ch in message:
                self.send_morse_char(ch)
                time.sleep(0.2)  # gap between letters
        else:
            for ch in message:
                self.send_byte(ord(ch), duration_ms=50)

    def send_byte(self, byte: int, duration_ms=50):
        for bit in format(byte, '08b'):
            self.send_bit(int(bit), duration_ms)

    def cleanup(self):
        self.pwm.stop()
        GPIO.cleanup(self.pin)


class AcousticReceiver:
    def __init__(self, mic_pin=0, adc_channel=0, threshold=0.3, mode='audible'):
        """
        Uses an analog microphone connected to ADC (e.g., MCP3008).
        For ultrasonic, use a 40kHz envelope detector circuit.
        """
        self.threshold = threshold
        self.mode = mode
        try:
            import Adafruit_MCP3008
            self.adc = Adafruit_MCP3008.MCP3008(clk=18, cs=25, miso=23, mosi=24)
        except ImportError:
            print("MCP3008 not found. Using mock ADC.")
            self.adc = None

    def read_sound_level(self) -> float:
        """Return 0-1 normalized sound amplitude."""
        if self.adc:
            raw = self.adc.read_adc(0)  # channel 0
            return raw / 1023.0
        else:
            import random
            return random.uniform(0, 0.5)

    def detect_tone(self) -> bool:
        """Return True if sound > threshold (tone present)."""
        return self.read_sound_level() > self.threshold

    def receive_bit(self, timeout=1.0) -> Optional[int]:
        start = time.time()
        while time.time() - start < timeout:
            if self.detect_tone():
                return 1
            time.sleep(0.01)
        return 0

    def receive_byte(self) -> Optional[int]:
        bits = []
        for _ in range(8):
            bit = self.receive_bit(timeout=0.2)
            bits.append(str(bit))
            time.sleep(0.05)  # bit period
        return int(''.join(bits), 2) if len(bits) == 8 else None

    def receive_message(self, max_len=20) -> str:
        chars = []
        for _ in range(max_len):
            b = self.receive_byte()
            if b is None or b == 0:
                break
            chars.append(chr(b))
        return ''.join(chars)
