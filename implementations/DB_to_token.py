import csv
import hashlib
import requests
from typing import Dict, Optional, Tuple

class FailureDatabase:
    def __init__(self, base_url="https://raw.githubusercontent.com/JinnZ2/Component-failure-repurposing-database/main/"):
        self.base_url = base_url
        self.failure_map = {}  # (component_type, token) -> (failure_mode, action, effectiveness)
        self._load_matrices()

    def _load_matrices(self):
        # Load failure_mode_matrix.csv
        fmm_url = self.base_url + "matrices/failure_mode_matrix.csv"
        resp = requests.get(fmm_url)
        if resp.status_code == 200:
            reader = csv.DictReader(resp.text.splitlines())
            for row in reader:
                comp = row.get('component', '').lower()
                mode = row.get('failure_mode', '')
                # Generate token from failure mode string (deterministic)
                token = self._failure_to_token(comp, mode)
                # Load repurpose effectiveness
                eff_url = self.base_url + "matrices/repurpose_effectiveness.csv"
                eff_resp = requests.get(eff_url)
                action = "log_only"  # default
                effectiveness = 0.0
                if eff_resp.status_code == 200:
                    eff_reader = csv.DictReader(eff_resp.text.splitlines())
                    for eff_row in eff_reader:
                        if eff_row.get('component', '').lower() == comp and eff_row.get('failure_mode', '') == mode:
                            action = eff_row.get('recommended_action', 'log_only')
                            effectiveness = float(eff_row.get('effectiveness', 0))
                            break
                self.failure_map[(comp, token)] = (mode, action, effectiveness)
        else:
            print("Warning: Could not load failure_mode_matrix.csv, using fallback mapping")

    def _failure_to_token(self, component: str, failure_mode: str) -> str:
        """Deterministic token from component+failure (for database lookup)."""
        h = hashlib.md5(f"{component}:{failure_mode}".encode()).hexdigest()
        vertex = f"{int(h[0],16) % 8:03b}"
        operator = "|" if "short" in failure_mode or "open" in failure_mode else "/"
        sym_idx = int(h[1],16) % 4
        symbol = ["O","I","X","Δ"][sym_idx]
        return f"{vertex}{operator}{symbol}"

    def lookup(self, component_type: str, token: str) -> Optional[Tuple[str, str, float]]:
        """Return (failure_mode, action, effectiveness) if token matches a known failure."""
        return self.failure_map.get((component_type.lower(), token))
