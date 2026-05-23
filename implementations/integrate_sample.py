"""
Integration Sample
==================
Shows how GeometricMonitoringSystem connects: token buffer -> processing
loop -> dependency detection -> failure database lookup -> repurpose action.

This is a reference snippet, not a standalone script.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from geometric_monitoring_engine import (
    GeometricMonitoringSystem,
    TokenBuffer,
    GeometricProcessingLoop,
    AISelfDiagnosis,
    value_to_token,
    lookup_failure,
)


class IntegratedMonitoringSystem(GeometricMonitoringSystem):
    """Extended system with failure-database-driven repurpose dispatch."""

    def __init__(self, cube_side=4):
        super().__init__(cube_side)
        self.component_last_token = {}
        # Re-register dependency callback with lookup
        self.processing.dependency_callbacks.clear()
        self.processing.on_dependency(self._on_dependency_with_lookup)

    def feed_sensor(self, component_id: str, value: float,
                    units: str, comp_type: str):
        token = value_to_token(value, units, comp_type)
        self.token_buffer.push(component_id, token)
        self.component_last_token[component_id] = (token, comp_type)

    def _on_dependency_with_lookup(self, prev_idx, curr_idx):
        print(f"DEPENDENCY: Cube {curr_idx} repeats cube {prev_idx}")
        for comp_id, (token, comp_type) in self.component_last_token.items():
            mode = lookup_failure(comp_type, token)
            if mode:
                print(f"  {comp_id} matches failure '{mode}'")
                self._execute_repurpose(comp_id, mode)

    def _execute_repurpose(self, component_id: str, action: str):
        """Dispatch repurpose action (fallback channel, mode switch, etc.)."""
        print(f"  Executing repurpose '{action}' for {component_id}")
        dispatch = {
            "optical_fallback": "Blinking LED in SOS pattern...",
            "rf_beacon":        "Transmitting RF beacon (OOK)...",
            "acoustic_alarm":   "Sounding piezo buzzer...",
            "magnetic_coupling": "Engaging magnetic loop coupling...",
            "thermal_heater":   "Activating resistor heater...",
        }
        print(f"    {dispatch.get(action, f'Logging action: {action}')}")
