"""
Physical Sensor Base Class
==========================
Abstract base for all simulated component sensors in the database.
Each sensor returns a standardised dict from ``sample()`` that the
geometric monitoring engine can convert to octahedral tokens.
"""

import time
import random
from abc import ABC, abstractmethod
from typing import Dict, Any


class PhysicalSensor(ABC):
    """
    Base class for hardware or simulated component sensors.

    Subclasses must implement ``sample()`` returning a dict with at least::

        {
            "type":          str,    # component type name
            "mode":          str,    # current failure mode or "none"
            "health_score":  float,  # 0.0 (failed) to 1.0 (nominal)
            "drift_pct":     float,  # deviation from nominal (%)
            "v":             float,  # voltage reading
            "i":             float,  # current reading
            "t":             float,  # temperature (deg C)
            "salvageable":   bool,   # True if repurpose-viable
        }
    """

    @abstractmethod
    def sample(self, env: dict = None) -> Dict[str, Any]:
        ...
