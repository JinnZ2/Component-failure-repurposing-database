# harm.py — energy_english harm reader
# CC0. stdlib only. phone-buildable.
#
# reads a signature, does not pass a verdict.
# harm here == the §1 invariant read on a coupled system:
#   draw_rate > regen_rate, cost exported through coupling, inflating per order.
#
# names_no: [intent, actor, should]. the reader returns numbers and a shape.
# what to do about the shape is not the reader's to say.

from dataclasses import dataclass, field


@dataclass
class Node:
    draw: float          # rate a node draws down capacity
    regen: float         # rate it regenerates capacity

    def local_imbalance(self):
        # exported cost = draw outrunning regen. never negative:
        # a node in surplus exports nothing.
        return max(0.0, self.draw - self.regen)


@dataclass
class Coupling:
    src: str
    dst: str
    transfer: float      # fraction of src's exported cost that reaches dst
    sensitivity: float   # how much arriving cost degrades dst's regen,
                         # inducing new local imbalance downstream


@dataclass
class System:
    nodes: dict          # name -> Node
    couplings: list = field(default_factory=list)


def read(system, orders=3):
    """
    return the harm signature. no label attached.

    signature:
      local        : per-node draw-minus-regen imbalance (order 0)
      per_order    : total induced imbalance at each order outward
      displaced    : cost moved through coupling, not just held local
      inflates     : each order's total exceeds the one before it
    """
    local = {name: n.local_imbalance() for name, n in system.nodes.items()}

    # order 0: cost sitting local, before any coupling fires
    export = dict(local)
    per_order = [sum(export.values())]

    for _ in range(orders):
        induced = {name: 0.0 for name in system.nodes}
        for c in system.couplings:
            arriving = export.get(c.src, 0.0) * c.transfer
            # arriving cost degrades dst's regen -> new local imbalance.
            # this is the mechanism that lets magnitude grow instead of
            # dissipate: displaced cost re-becomes draw at the next node.
            induced[c.dst] += arriving * c.sensitivity
        per_order.append(sum(induced.values()))
        export = induced

    displaced = any(c.transfer > 0 for c in system.couplings) and per_order[0] > 0
    # inflates == a later order exceeds order 0 (2nd/3rd > 1st).
    # NOT "grows without end" — a finite chain always tails to 0 as cost
    # runs off the modeled edge; that terminal 0 is not a disconfirmation.
    inflates = displaced and max(per_order[1:]) > per_order[0]

    return {
        "local": local,
        "per_order": per_order,
        "displaced": displaced,
        "inflates": inflates,
    }


# --- self-test (assert-based, stdlib only) ---------------------------------

def _t_surplus_exports_nothing():
    s = System({"a": Node(draw=1.0, regen=3.0)})
    sig = read(s)
    assert sig["local"]["a"] == 0.0
    assert sig["per_order"][0] == 0.0
    assert not sig["displaced"]
    assert not sig["inflates"]


def _t_local_imbalance_no_coupling_does_not_displace():
    s = System({"a": Node(draw=3.0, regen=1.0)})
    sig = read(s)
    assert sig["local"]["a"] == 2.0
    assert not sig["displaced"]          # no coupling -> nowhere to export
    assert not sig["inflates"]


def _t_dissipating_coupling_does_not_inflate():
    # cost crosses coupling but decays (low transfer * sensitivity)
    s = System(
        {"a": Node(3.0, 1.0), "b": Node(1.0, 1.0), "c": Node(1.0, 1.0)},
        [Coupling("a", "b", transfer=0.3, sensitivity=0.3),
         Coupling("b", "c", transfer=0.3, sensitivity=0.3)],
    )
    sig = read(s)
    assert sig["displaced"]
    assert not sig["inflates"]           # magnitude shrinks per order

def _t_amplifying_coupling_inflates():
    # arriving cost degrades regen enough that downstream imbalance
    # exceeds upstream -> inflation per order. this is the signature.
    s = System(
        {"a": Node(3.0, 1.0), "b": Node(1.0, 1.0), "c": Node(1.0, 1.0)},
        [Coupling("a", "b", transfer=1.0, sensitivity=2.0),
         Coupling("b", "c", transfer=1.0, sensitivity=2.0)],
    )
    sig = read(s)
    assert sig["displaced"]
    assert sig["inflates"]
    assert sig["per_order"][2] > sig["per_order"][1] > sig["per_order"][0]


def _run():
    for name, fn in sorted(globals().items()):
        if name.startswith("_t_"):
            fn()
            print("ok", name)
    print("all pass")


if __name__ == "__main__":
    _run()
