# cyclic_repurpose_controller.py — repurposing framework using Cyclic physics.
# CC0. stdlib + cyclic_interpreter.py.
#
# Connects the rigidification sensor to the Cyclic interpreter.
# Fields represent component nodes; repurposing = regeneration/symbiosis.

from cyclic_interpreter import CyclicalInterpreter

class CyclicSystem:
    def __init__(self):
        self.interp = CyclicalInterpreter()
        self.tick = 0

    def add_node(self, name, draw, regen):
        """Create a field with energy = regen, and store draw as a property for erosion."""
        self.interp.execute(f"create {name} {regen}")
        # We'll store draw as a user-defined attribute on the field state.
        self.interp.fields[name].draw = draw

    def step(self):
        """Advance one tick: apply natural decay (failure) and update metrics."""
        for name, field in self.interp.fields.items():
            # Decay equals draw rate minus any surplus, but energy never negative.
            decay_amount = field.draw * 0.1  # scale factor
            if decay_amount > 0:
                self.interp.execute(f"∂decay({name}, {decay_amount})")
        self.tick += 1
        return self.metrics()

    def metrics(self):
        """Return DOF, continuation, reversal as per rigidification sensor."""
        dof = sum(1 for f in self.interp.fields.values() if f.energy > getattr(f, 'draw', 0))
        continuation = sum(f.draw for f in self.interp.fields.values())  # total draw
        reversal = sum(f.initial_energy - f.energy for f in self.interp.fields.values())  # lost capacity
        return dof, continuation, reversal

    def repurpose(self, from_node, to_node, amount):
        """Directed transfer of surplus energy: MOVE <amount> FROM <from> TO <to>."""
        self.interp.execute(f"COBOL:MOVE {amount} FROM {from_node} TO {to_node}")

    def entangle(self, a, b):
        """Knowledge entanglement: regen on one boosts the other."""
        self.interp.execute(f"⊗({a}, {b})")
