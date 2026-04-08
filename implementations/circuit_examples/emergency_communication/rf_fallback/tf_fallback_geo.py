"""
RF OOK transmitter using a 433MHz module (e.g., FS1000A).
Data pin connected to GPIO.
"""

import RPi.GPIO as GPIO
import time

class RFTransmitter:
    def __init__(self, data_pin=27, protocol='raw'):
        self.pin = data_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        self.protocol = protocol

    def send_bit(self, bit):
        GPIO.output(self.pin, bit)
        time.sleep(0.0003)  # 300us pulse (typical for OOK)

    def send_byte(self, byte):
        for bit in format(byte, '08b'):
            self.send_bit(int(bit))

    def send_message(self, message: str, preamble=[1,1,1,1,1]):
        # Send preamble to wake receiver
        for b in preamble:
            self.send_bit(b)
        time.sleep(0.001)
        for ch in message:
            self.send_byte(ord(ch))
        self.send_bit(0)  # stop bit

    def cleanup(self):
        GPIO.cleanup(self.pin)

# Example receiver (using RTL-SDR or simple module) would need a separate script.
