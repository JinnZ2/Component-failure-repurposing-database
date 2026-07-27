# vendor/cyclic

This directory contains a copy of the Cyclic Programming interpreter
from https://github.com/JinnZ2/cyclic-programming. It is used solely
as a physics engine for energy-conserving repurposing actions.
It is not modified here; upstream updates should be pulled manually.

Pinned to upstream commit `7d9054a` (retrieved 2026-07-27). Provenance,
per-file SHA-256 sums, and the list of upstream files left out are in
[`UPSTREAM.json`](UPSTREAM.json).

## Contents

| File | Provides |
|------|----------|
| `cyclic_interpreter.py` | `CyclicalInterpreter` — fields carrying an `EnergyState`, with decay, regeneration, directed transfer, entanglement, and symbiosis |
| `LICENSE` | Upstream MIT license (© 2025 JinnZ2) |

Standard library only, Python 3.9 or newer.

Only the interpreter is vendored. The rest of the upstream repository —
demos, the language-ecosystem scripts, and the `harm.py` / `simulator.py`
pair — is out of scope here and deliberately not copied.

## Interface

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor" / "cyclic"))

from cyclic_interpreter import CyclicalInterpreter  # noqa: E402
```

The upstream README documents the language, not the Python surface. What
matters when calling it directly:

- Create fields with `interp.create_field(name, initial_energy)`. There is no
  `create` statement in the language grammar.
- `interp.fields[name].energy` is an `EnergyState`, not a float. The scalar is
  `interp.fields[name].energy.total_energy`.
- Operations execute as source text: `interp.execute("∂decay(f, 0.1)")`,
  `interp.execute("∮regenerate(f, 5)")`,
  `interp.execute("COBOL:MOVE 30 FROM src TO dst")`, `interp.execute("⊗(a, b)")`.
- `COBOL:MOVE` conserves energy exactly — the source loses what the target
  gains, with entropy charged separately. Transfers are clamped to 90 % of
  source energy.
- `∂decay` takes a *fraction*, not an absolute amount. Rates above 1.0 drive
  energy negative, and a negative-energy field makes transfers run backwards,
  since the clamp `min(amount, energy * 0.9)` goes negative. Keep decay rates
  in the 0.0–1.0 range.

## Updating

Pull by hand — there is no submodule and no package pin:

```sh
git clone --depth 1 https://github.com/JinnZ2/cyclic-programming /tmp/cyclic
cp /tmp/cyclic/cyclic_interpreter.py /tmp/cyclic/LICENSE vendor/cyclic/
```

Then refresh `commit`, `retrieved`, and the `sha256` values in `UPSTREAM.json`.

Do not edit files in this directory. Anything that needs different behaviour
belongs in a wrapper outside `vendor/`, so the next pull stays a straight copy.
