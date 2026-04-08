class GeometricMonitoringSystem:
    def __init__(self, cube_side=4):
        # ... existing init ...
        self.optical_tx = None
        self.rf_tx = None

    def _execute_repurpose(self, component_id: str, action: str):
        print(f"   → Executing repurpose action '{action}' for {component_id}")
        if action == "optical_fallback":
            if self.optical_tx is None:
                from optical_fallback import OpticalTransmitter
                self.optical_tx = OpticalTransmitter(led_pin=18)
            self.optical_tx.blink_sos()  # or send_message("FAILURE")
        elif action == "rf_beacon":
            if self.rf_tx is None:
                from rf_fallback import RFTransmitter
                self.rf_tx = RFTransmitter(data_pin=27)
            self.rf_tx.send_message("FAIL:resistor_drift")
        elif action == "acoustic_alarm":
            # Use piezo buzzer (simple GPIO tone)
            import RPi.GPIO as GPIO
            buzzer_pin = 23
            GPIO.setup(buzzer_pin, GPIO.OUT)
            for _ in range(3):
                GPIO.output(buzzer_pin, 1)
                time.sleep(0.2)
                GPIO.output(buzzer_pin, 0)
                time.sleep(0.1)
            GPIO.cleanup(buzzer_pin)
        elif action == "log_only":
            print("      Logging only – no hardware action.")
        else:
            print(f"      Unknown action '{action}', logging only.")
