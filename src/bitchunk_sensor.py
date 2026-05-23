import time
from sensors.physical_sensor import PhysicalSensor


class BitChunkSensor(PhysicalSensor):
    """Emits tokens from a binary string by chunking into 6‑bit pieces."""
    def __init__(self, binary_string: str, repeat_interval: float = 1.0):
        self.binary = binary_string
        self.repeat_interval = repeat_interval
        self.last_send = 0
        self.pos = 0
        # Pad to multiple of 6
        if len(self.binary) % 6 != 0:
            self.binary = self.binary.ljust((len(self.binary) + 5) // 6 * 6, '0')

    def sample(self, env=None) -> dict:
        now = time.time()
        if now - self.last_send >= self.repeat_interval:
            # Get next 6 bits
            chunk = self.binary[self.pos:self.pos+6]
            self.pos = (self.pos + 6) % len(self.binary)
            self.last_send = now
            # Convert chunk to token
            vertex = chunk[:3]
            op_bit = chunk[3]
            sym_bits = chunk[4:6]
            operator = '|' if op_bit == '1' else '/'
            sym_map = {'00':'O','01':'I','10':'X','11':'Δ'}
            symbol = sym_map.get(sym_bits, 'O')
            token = f"{vertex}{operator}{symbol}"
            # Return as a geometry dict (health=100% unless we want to encode something else)
            return {
                "type": "binary_chunk",
                "mode": "data",
                "health_score": 1.0,
                "drift_pct": 0,
                "v": 0,
                "i": 0,
                "t": 25,
                "salvageable": False,
                "geometric_token": token
            }
        else:
            # No new data
            return {"type": "binary_chunk", "mode": "idle", "health_score": 1.0}
