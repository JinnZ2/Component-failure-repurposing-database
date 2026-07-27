# repurpose_controller.py — active repurposing actions in the dynamical model.
# CC0. stdlib only. phone-buildable. imports simulator.py.
#
# Adds a RepurposeAction that can be scheduled per tick, consuming from a
# knowledge-base reserve to heal a node's regen.  The reserve can itself
# be eroded by systemic draw, modelling the maintenance burden on the DB.

from harm import System, Node, Coupling
import simulator

class RepurposeReserve:
    """The cumulative repurposing knowledge — a limited resource."""
    def __init__(self, initial=10.0, decay_rate=0.1):
        self.value = initial
        self.initial = initial
        self.decay_rate = decay_rate   # passive obsolescence per tick

    def draw(self, amount):
        self.value = max(0.0, self.value - amount)
        return self.value

    def tick(self):
        """Passive decay of unused knowledge."""
        self.value = max(0.0, self.value - self.decay_rate)

def run_with_repurposing(system, ticks=20, erosion=1.0, regen_rate=0.0,
                         repurpose_reserve=None, controller=None):
    """
    Like simulator.run() but allows a controller function to issue
    repurpose actions each tick.  The controller receives (tick, system,
    reserve) and returns a list of (node_name, heal_amount) tuples.
    """
    regen0 = {n: nd.regen for n, nd in system.nodes.items()}
    trace = []
    locked_at = None

    if repurpose_reserve is None:
        repurpose_reserve = RepurposeReserve(initial=float('inf'), decay_rate=0)

    for t in range(ticks):
        # 1. Controller may intervene before erosion
        if controller:
            actions = controller(t, system, repurpose_reserve)
            for node_name, heal in actions:
                if repurpose_reserve.value >= heal:
                    system.nodes[node_name].regen += heal
                    repurpose_reserve.value -= heal
                    # Optionally cap regen at initial? Keep simple.
        # 2. Standard step
        exported, induced = simulator.step(system, erosion)
        # 3. Apply regeneration (natural recovery)
        if regen_rate > 0:
            for n, nd in system.nodes.items():
                nd.regen = min(regen0[n], nd.regen + regen_rate)
        # 4. Passive decay of the reserve
        repurpose_reserve.tick()

        # metrics
        continuation = sum(exported.values())
        reversal = sum(regen0[n] - nd.regen for n, nd in system.nodes.items())
        dof = sum(1 for n, nd in system.nodes.items() if nd.regen > nd.draw)

        prev = trace[-1] if trace else None
        d_cont = continuation - prev["continuation"] if prev else continuation
        d_rev = reversal - prev["reversal"] if prev else reversal

        row = {
            "t": t,
            "dof": dof,
            "continuation": round(continuation,4),
            "reversal": round(reversal,4),
            "d_continuation": round(d_cont,4),
            "d_reversal": round(d_rev,4),
        }
        trace.append(row)
        if locked_at is None and reversal > continuation and d_rev > d_cont:
            locked_at = t

    return trace, locked_at, repurpose_reserve


# Example controller that uses 50% of remaining reserve to heal the node
# with the largest deficit, but only if DOF < 2 and reserve > 0.
def deficit_trigger_controller(t, system, reserve):
    if reserve.value <= 0:
        return []
    dof = sum(1 for nd in system.nodes.values() if nd.regen > nd.draw)
    if dof < 2:
        # find node with largest local imbalance
        worst_node = max(system.nodes, key=lambda n: system.nodes[n].local_imbalance())
        heal_amount = min(reserve.value * 0.5, 1.0)  # spend up to 0.5*reserve, max 1.0 per tick
        return [(worst_node, heal_amount)]
    return []


# Demo on the dependency-hell system with a finite repurpose reserve
if __name__ == "__main__":
    sys = System(
        {"A": Node(3.0, 1.5), "B": Node(2.0, 2.5), "C": Node(1.5, 2.0)},
        [Coupling("A", "B", 1.0, 2.0), Coupling("B", "C", 0.9, 1.5)]
    )
    reserve = RepurposeReserve(initial=4.0, decay_rate=0.05)
    trace, lock, reserve = run_with_repurposing(
        sys, ticks=20, erosion=1.0, regen_rate=0.05,
        repurpose_reserve=reserve, controller=deficit_trigger_controller
    )
    print("t | dof | contin | reversal | reserve")
    for r in trace:
        print(f"{r['t']:<2}  {r['dof']}    {r['continuation']:<7} {r['reversal']:<9} {reserve.value:.2f}")
    print(f"Locked at: {lock}")
    print(f"Final reserve: {reserve.value:.2f} (initial {reserve.initial})")
