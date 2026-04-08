# hardware_bridge_encoder.py
import hashlib

class HardwareBridgeEncoder:
    """
    Maps physical parameters to a 39-bit binary signature.
    Then can convert that signature to a sequence of octahedral tokens.
    """
    def __init__(self):
        self.bits = 39

    def from_geometry(self, geometry: dict) -> 'HardwareBridgeEncoder':
        """
        Accepts a dict with keys:
          component_type, failure_mode, health_score, drift_pct,
          voltage_v, current_a, temperature_c, salvageable
        Returns self for chaining.
        """
        # Combine all values into a deterministic string
        data_str = (
            f"{geometry.get('component_type','')}"
            f"{geometry.get('failure_mode','')}"
            f"{geometry.get('health_score',0):.3f}"
            f"{geometry.get('drift_pct',0):.3f}"
            f"{geometry.get('voltage_v',0):.3f}"
            f"{geometry.get('current_a',0):.3f}"
            f"{geometry.get('temperature_c',25):.3f}"
            f"{geometry.get('salvageable',False)}"
        )
        # SHA‑256 then take first 39 bits
        h = hashlib.sha256(data_str.encode()).digest()
        # Convert to integer, mask to 39 bits
        value = int.from_bytes(h, 'big') & ((1 << self.bits) - 1)
        self.binary_str = f"{value:0{self.bits}b}"
        return self

    def to_binary(self) -> str:
        """Return the full 39‑bit binary string."""
        return self.binary_str

    def to_octahedral_tokens(self) -> list:
        """
        Chunk the 39‑bit binary into 6‑bit octahedral tokens.
        (6 bits = vertex(3) + operator(1) + symbol(2))
        Returns a list of token strings like "001|O".
        """
        tokens = []
        full = self.binary_str
        # Pad to multiple of 6
        if len(full) % 6 != 0:
            full = full.ljust((len(full) + 5) // 6 * 6, '0')
        for i in range(0, len(full), 6):
            chunk = full[i:i+6]
            vertex = chunk[:3]
            op_bit = chunk[3]
            sym_bits = chunk[4:6]
            operator = '|' if op_bit == '1' else '/'
            sym_map = {'00':'O','01':'I','10':'X','11':'Δ'}
            symbol = sym_map.get(sym_bits, 'O')
            tokens.append(f"{vertex}{operator}{symbol}")
        return tokens
