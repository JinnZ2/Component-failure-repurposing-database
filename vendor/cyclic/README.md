# vendor/cyclic

This directory contains a copy of the Cyclic Programming interpreter
from https://github.com/JinnZ2/cyclic-programming. It is used solely
as a physics engine for energy-conserving repurposing actions.
It is not modified here; upstream updates should be pulled manually.

Pinned to upstream commit `7d9054a` (retrieved 2026-07-27). Exact provenance,
per-file SHA-256 sums, and the list of upstream files deliberately left out are
in [`UPSTREAM.json`](UPSTREAM.json).

## Contents

| File | Provides |
|------|----------|
| `cyclic_interpreter.py` | `CyclicalInterpreter` — fields carrying an `EnergyState`, with decay, regeneration, directed transfer, entanglement, and symbiosis |
| `harm.py` | `Node`, `Coupling`, `System`, `read()` — a static read of draw-versus-regen imbalance across a coupled system |
| `simulator.py` | `step()`, `run()` — advances the `harm` reading through time so displaced cost erodes the receiving node's regen |
| `LICENSE` | Upstream MIT license (© 2025 JinnZ2) |

Standard library only, Python 3.9 or newer. Nothing here is imported at package
import time — modules that want the engine put this directory on `sys.path`
themselves.

## Why it is vendored

Repurposing decisions in this database are budget-limited: a failed component
is re-tasked by moving capacity from somewhere else, and the accounting has to
balance or the recommendation is fiction. The Cyclic engine supplies that
accounting. `FieldState.directed_transfer` moves an exact amount from source to
target — the source loses precisely what the target gains, with entropy charged
separately — so a repurposing action can be scored instead of assumed.

`harm.py` and `simulator.py` supply the complementary read: whether a system of
coupled components is still shedding cost locally or has crossed into a regime
where reversing the damage costs more than continuing. `repurpose_controller.py`
at the repository root builds on both, spending from a finite `RepurposeReserve`
to heal node regen.

## Using it

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor" / "cyclic"))

from harm import System, Node, Coupling      # noqa: E402
import simulator                             # noqa: E402
from cyclic_interpreter import CyclicalInterpreter  # noqa: E402
```

Interpreter API notes, since the upstream README documents the language rather
than the Python surface:

- Fields are created with `interp.create_field(name, initial_energy)`. There is
  no `create` statement in the language grammar.
- `interp.fields[name].energy` is an `EnergyState`, not a float. Read the scalar
  as `interp.fields[name].energy.total_energy`.
- Operations execute as source text: `interp.execute("∂decay(f, 0.1)")`,
  `interp.execute("∮regenerate(f, 5)")`,
  `interp.execute("COBOL:MOVE 30 FROM src TO dst")`, `interp.execute("⊗(a, b)")`.
- `∂decay` takes a *fraction*, not an absolute amount. Rates above 1.0 drive
  energy negative, and a negative-energy field makes `directed_transfer` run
  backwards, because the transfer clamp `min(amount, energy * 0.9)` goes
  negative. Keep decay rates in the 0.0–1.0 range.

## Updating

Pull upstream by hand — there is no submodule and no package pin:

```sh
git clone --depth 1 https://github.com/JinnZ2/cyclic-programming /tmp/cyclic
cp /tmp/cyclic/{cyclic_interpreter.py,harm.py,simulator.py,LICENSE} vendor/cyclic/
```

Then refresh `commit`, `retrieved`, and the `sha256` values in `UPSTREAM.json`,
and re-run the self-tests:

```sh
python3 vendor/cyclic/harm.py         # asserts, prints "all pass"
python3 vendor/cyclic/simulator.py    # asserts, then a demo trace
python3 repurpose_controller.py       # end-to-end via the vendored modules
```

Do not edit files in this directory. Anything that needs different behaviour
belongs in a wrapper outside `vendor/`, so the next upstream pull stays a
straight copy.
