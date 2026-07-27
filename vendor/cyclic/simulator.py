# simulator.py — steps the harm reader forward in time.
# CC0. stdlib only. phone-buildable. imports harm.py.
#
# harm.read is a snapshot. this makes it dynamical: displaced cost
# actually erodes the receiving node's regen, so the deficit compounds.
# that persistence IS the §1 invariant — "cheaper to continue than reverse"
# stops being a phrase and becomes a measured divergence.
#
# time carries the propagation: one coupling hop per tick, so order == tick.
# names_no: [intent, actor, should]. reports state, judges nothing.

from harm import Node, Coupling, System


def step(system, erosion=1.0):
    """one tick. returns (exported, induced). mutates regen in place."""
    exported = {n: nd.local_imbalance() for n, nd in system.nodes.items()}
    induced = {n: 0.0 for n in system.nodes}
    for c in system.couplings:
        induced[c.dst] += exported[c.src] * c.transfer * c.sensitivity
    # arriving cost erodes regen — persists into next tick. this is the
    # feedback that lets the cascade feed itself instead of settling.
    for n, amt in induced.items():
        system.nodes[n].regen = max(0.0, system.nodes[n].regen - amt * erosion)
    return exported, induced


def run(system, ticks=20, erosion=1.0):
    """
    step the system and record the §3 tells over time.

    per tick:
      dof            : nodes still in surplus (regen > draw) — off-ramps open
      continuation   : current total imbalance — the bill this tick
      reversal       : cumulative eroded regen — capacity you'd rebuild to undo
      d_continuation : change in continuation vs last tick
      d_reversal     : change in reversal vs last tick
    locked_at:
      first tick where reversal outpaces continuation AND exceeds it —
      the §1 threshold crossing, past which pruning stops being cheap.
    """
    regen0 = {n: nd.regen for n, nd in system.nodes.items()}
    trace = []
    locked_at = None

    for t in range(ticks):
        exported, induced = step(system, erosion)

        continuation = sum(exported.values())
        reversal = sum(regen0[n] - nd.regen for n, nd in system.nodes.items())
        dof = sum(1 for n, nd in system.nodes.items() if nd.regen > nd.draw)

        prev = trace[-1] if trace else None
        d_cont = continuation - prev["continuation"] if prev else continuation
        d_rev = reversal - prev["reversal"] if prev else reversal

        row = {
            "t": t,
            "dof": dof,
            "continuation": round(continuation, 4),
            "reversal": round(reversal, 4),
            "d_continuation": round(d_cont, 4),
            "d_reversal": round(d_rev, 4),
        }
        trace.append(row)

        if locked_at is None and reversal > continuation and d_rev > d_cont:
            locked_at = t

    return {"trace": trace, "locked_at": locked_at}


# --- self-test -------------------------------------------------------------

def _t_all_surplus_never_locks():
    s = System({"a": Node(1.0, 3.0), "b": Node(1.0, 3.0)},
               [Coupling("a", "b", 1.0, 1.0)])
    out = run(s, ticks=10)
    assert out["locked_at"] is None
    assert all(r["dof"] == 2 for r in out["trace"])   # both off-ramps stay open


def _t_amplifying_chain_locks_and_sheds_dof():
    s = System({"a": Node(3.0, 1.0), "b": Node(1.0, 2.0), "c": Node(1.0, 2.0)},
               [Coupling("a", "b", 1.0, 2.0), Coupling("b", "c", 1.0, 2.0)])
    out = run(s, ticks=15)
    assert out["locked_at"] is not None                # threshold crossed
    assert out["trace"][-1]["dof"] < out["trace"][0]["dof"]  # off-ramps closed
    # crossing holds AT the lock tick; after full erosion metrics saturate
    # to a shared cap, so the final tick is not where you read it.
    L = out["locked_at"]
    assert out["trace"][L]["reversal"] > out["trace"][L]["continuation"]


def _t_reversal_outpaces_continuation_after_lock():
    s = System({"a": Node(3.0, 1.0), "b": Node(1.0, 2.0), "c": Node(1.0, 2.0)},
               [Coupling("a", "b", 1.0, 2.0), Coupling("b", "c", 1.0, 2.0)])
    out = run(s, ticks=15)
    L = out["locked_at"]
    after = out["trace"][L]
    assert after["d_reversal"] > after["d_continuation"]


def _run():
    for name, fn in sorted(globals().items()):
        if name.startswith("_t_"):
            fn()
            print("ok", name)
    print("all pass")


def _demo():
    print("\n--- demo: amplifying chain ---")
    s = System({"a": Node(3.0, 1.0), "b": Node(1.0, 2.0), "c": Node(1.0, 2.0)},
               [Coupling("a", "b", 1.0, 2.0), Coupling("b", "c", 1.0, 2.0)])
    out = run(s, ticks=12)
    hdr = "t  dof  contin  revers  dCont  dRev"
    print(hdr)
    for r in out["trace"]:
        print(f'{r["t"]:<2} {r["dof"]:<4} {r["continuation"]:<7} '
              f'{r["reversal"]:<7} {r["d_continuation"]:<6} {r["d_reversal"]}')
    print("locked_at:", out["locked_at"])


if __name__ == "__main__":
    _run()
    _demo()
