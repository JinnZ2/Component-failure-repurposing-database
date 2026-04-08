class GeometricMonitoringSystem:
    def __init__(self, cube_side=4):
        self.token_buffer = TokenBuffer()
        self.processing = GeometricProcessingLoop(self.token_buffer, cube_side)
        self.ai_diag = AISelfDiagnosis(interval_sec=3, cube_side=3)
        self.db = FailureDatabase()
        self.component_last_token = {}  # component_id -> last token
        self.processing.on_dependency(self._on_dependency)

    def feed_sensor(self, component_id: str, value: float, units: str, comp_type: str):
        token = value_to_token(value, units, comp_type)
        self.token_buffer.push(component_id, token)
        self.component_last_token[component_id] = token

    def _on_dependency(self, prev_idx, curr_idx):
        print(f"🔔 GEOMETRIC DEPENDENCY: Cube {curr_idx} repeats cube {prev_idx}")
        # For each component that contributed to this cube (we need to know which components were in the cube)
        # Simplified: for now, check the last token of each component
        for comp_id, token in self.component_last_token.items():
            # Determine component type from registration (simplified: extract from comp_id)
            comp_type = comp_id.split('_')[0] if '_' in comp_id else comp_id
            failure_info = self.db.lookup(comp_type, token)
            if failure_info:
                mode, action, effectiveness = failure_info
                print(f"   → Component {comp_id} matches failure '{mode}' (eff={effectiveness})")
                self._execute_repurpose(comp_id, action)

    def _execute_repurpose(self, component_id: str, action: str):
        """Execute a repurposing action (fallback channel, mode switch, etc.)."""
        print(f"   → Executing repurpose action '{action}' for {component_id}")
        if action == "optical_fallback":
            # Example: blink an LED (GPIO write)
            print("      Blinking LED in SOS pattern...")
            # Here you would call hardware-specific code (e.g., RPi.GPIO, termux-gpio)
        elif action == "rf_beacon":
            print("      Transmitting RF beacon (OOK)...")
            # Use simple_ook_tx implementation
        elif action == "acoustic_alarm":
            print("      Sounding piezo buzzer...")
        elif action == "magnetic_coupling":
            print("      Engaging magnetic loop coupling...")
        elif action == "thermal_heater":
            print("      Activating resistor heater...")
        else:
            print(f"      Unknown action '{action}', logging only.")
