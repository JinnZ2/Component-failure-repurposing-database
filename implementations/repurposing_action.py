"""
Repurposing Action Dispatcher
==============================
Shows how the geometric monitoring system dispatches hardware actions
when a dependency (repeated failure cube) is detected.

Hardware imports (RPi.GPIO, optical_fallback, rf_fallback) are guarded
so the module loads safely on non-Raspberry Pi systems.
"""
import time


class RepurposeDispatcher:
    """Routes repurpose actions to hardware fallback channels."""

    def __init__(self):
        self.optical_tx = None
        self.rf_tx = None

    def execute(self, component_id: str, action: str):
        print(f"  Executing repurpose action '{action}' for {component_id}")

        if action == "optical_fallback":
            try:
                from implementations.optical_fallback import OpticalTransmitter
                if self.optical_tx is None:
                    self.optical_tx = OpticalTransmitter(led_pin=18)
                self.optical_tx.blink_sos()
            except ImportError:
                print("    [sim] LED SOS blink (no RPi.GPIO)")

        elif action == "rf_beacon":
            try:
                from implementations.rf_fallback import RFTransmitter
                if self.rf_tx is None:
                    self.rf_tx = RFTransmitter(data_pin=27)
                self.rf_tx.send_message(f"FAIL:{component_id}")
            except ImportError:
                print("    [sim] RF OOK beacon (no RPi.GPIO)")

        elif action == "acoustic_alarm":
            try:
                import RPi.GPIO as GPIO
                buzzer_pin = 23
                GPIO.setup(buzzer_pin, GPIO.OUT)
                for _ in range(3):
                    GPIO.output(buzzer_pin, 1)
                    time.sleep(0.2)
                    GPIO.output(buzzer_pin, 0)
                    time.sleep(0.1)
                GPIO.cleanup(buzzer_pin)
            except ImportError:
                print("    [sim] Piezo buzzer alarm (no RPi.GPIO)")

        elif action == "magnetic_coupling":
            print("    Engaging magnetic loop coupling...")

        elif action == "thermal_heater":
            print("    Activating resistor heater...")

        elif action == "log_only":
            print("    Logging only - no hardware action.")

        else:
            print(f"    Unknown action '{action}', logging only.")
