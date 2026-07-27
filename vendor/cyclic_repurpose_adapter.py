# cyclic_repurpose_adapter.py — controlled bridge to Cyclic Programming.
# CC0. stdlib only. phone-buildable.
#
# This adapter is the ONLY file that imports from the cyclic interpreter.
# All other modules use the functions defined here.

import os
import sys

# Optional import – graceful fallback
try:
    # Adjust path if cyclic interpreter is in vendor/cyclic/ or a submodule
    CYCLIC_PATH = os.path.join(os.path.dirname(__file__), "vendor", "cyclic")
    if CYCLIC_PATH not in sys.path:
        sys.path.insert(0, CYCLIC_PATH)
    from cyclic_interpreter import CyclicalInterpreter
    CYCLIC_AVAILABLE = True
except ImportError:
    CYCLIC_AVAILABLE = False


class CyclicRepurposeEngine:
    """
    Wraps the Cyclic interpreter (if available) or falls back to a
    simple energy‑conserving model. The interface is identical either way.
    """
    def __init__(self):
        if CYCLIC_AVAILABLE:
            self.interp = CyclicalInterpreter()
            self._fields = {}  # mirror for draw tracking
        else:
            self.interp = None
            self._fields = {}  # name -> {energy, initial, draw}

    def create_node(self, name, draw, regen):
        """Create a field/node with initial energy = regen."""
        if CYCLIC_AVAILABLE:
            self.interp.execute(f"create {name} {regen}")
            self.interp.fields[name].draw = draw
        else:
            self._fields[name] = {
                "energy": regen,
                "initial": regen,
                "draw": draw,
            }

    def apply_decay(self, name, amount):
        """Reduce energy by a fixed amount (failure/draw)."""
        if CYCLIC_AVAILABLE:
            self.interp.execute(f"∂decay({name}, {amount})")
        else:
            f = self._fields[name]
            f["energy"] = max(0.0, f["energy"] - amount)

    def regenerate(self, name, amount):
        """Increase energy (repair / regen surplus)."""
        if CYCLIC_AVAILABLE:
            self.interp.execute(f"∮regenerate({name}, {amount})")
        else:
            f = self._fields[name]
            f["energy"] += amount
            # No cap unless explicitly set; we trust the controller not to overflow

    def transfer(self, source, target, amount):
        """Directed transfer: source loses, target gains."""
        if CYCLIC_AVAILABLE:
            self.interp.execute(f"COBOL:MOVE {amount} FROM {source} TO {target}")
        else:
            sf = self._fields[source]
            tf = self._fields[target]
            actual = min(sf["energy"], amount)
            sf["energy"] -= actual
            tf["energy"] += actual

    def entangle(self, a, b):
        """Entangle two nodes – regeneration on one boosts the other."""
        if CYCLIC_AVAILABLE:
            self.interp.execute(f"⊗({a}, {b})")
        else:
            # Simple heuristic: share 50% of future regeneration between them
            # We'll store a flag and modify regenerate() later.
            # For now, we note it's a no‑op in fallback mode.
            pass

    def energy(self, name):
        """Return current energy of a node."""
        if CYCLIC_AVAILABLE:
            return self.interp.fields[name].energy
        else:
            return self._fields[name]["energy"]

    def surplus(self, name):
        """Energy minus draw (positive = surplus)."""
        if CYCLIC_AVAILABLE:
            node = self.interp.fields[name]
            return node.energy - node.draw
        else:
            f = self._fields[name]
            return f["energy"] - f["draw"]
