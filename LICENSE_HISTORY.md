# License history and scope

## Note 2026-10-14 — owner CC0 decision and scope

The owner directed that **Component-failure-repurposing-database** be
relicensed to CC0 on 2026-10-14. The root [`LICENSE`](./LICENSE) is the
standard CC0 1.0 Universal legal text supplied for this work order. That
CC0 dedication applies only to copyright and related rights that the owner
controls in eligible owner-authored material in this repository; it does not
purport to grant rights in material outside that scope.

Copies obtained before this date under the prior MIT license remain MIT for
those holders.

### Superseded root `LICENSE` (preserved verbatim)

The root `LICENSE` before this decision contained this complete statement:

```text
MIT License

Copyright (c) 2025 JinnZ2

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The following former current-license statements are also retained here rather
than silently erased:

- `CLAUDE.md`: `**License:** MIT`
- `scenario_engine/README.md`: `MIT (inherits from parent repository).`

The root README, `metadata.json`, `CITATION.cff`, and several internal source
headers already described CC0 before this root-license correction. They were
not treated as proof of ownership; they are now consistent current statements
for the owner-controlled scope described above.

### Prior reading-guide scope note (preserved verbatim)

The prior final `## In this repo` note in `READ_ME_THIS_WAY.md` was:

> Note 2026-10-14: Existing conflicting license labels remain unchanged and unresolved; this reading layer does not extend or settle any original license.

It is superseded only as a current scope note by the owner decision recorded
above. The note remains here as a dated record of the former, deliberately
limited guide scope.

## Provenance and third-party exceptions checked 2026-10-14

This review covered tracked license/attribution/COPYING/NOTICE references,
the reachable commit-author summary, `vendor/`, upstream metadata, and
per-file vendor checksums. It cannot prove the absence of undisclosed copying.

| Path | Source / author evidence | License or status | Current action |
|---|---|---|---|
| `vendor/cyclic/cyclic_interpreter.py` | `vendor/cyclic/UPSTREAM.json` pins `JinnZ2/cyclic-programming` commit `7d9054a40b09080f965bf63eba30353a703f643e`; recorded SHA-256 matches the checked file. `vendor/cyclic/README.md` calls it an unmodified upstream copy. | Upstream MIT; see adjacent `vendor/cyclic/LICENSE`. | **Exception:** not relicensed here; retained verbatim with its upstream MIT notice. |
| `vendor/cyclic/LICENSE` | Upstream metadata lists it as the upstream license; recorded SHA-256 matches. | MIT, copyright © 2025 JinnZ2. | **Exception:** retained verbatim; do not replace with CC0. |
| `vendor/cyclic/UPSTREAM.json` and `vendor/cyclic/README.md` | Pinned-source and checksum records for the same vendored package. | Provenance records; preserve with the vendored package. | Retained unchanged; the root CC0 statement does not rewrite the upstream package's licensing record. |
| `scenario_engine/couplers/__init__.py` | The header identifies `JinnZ2/Geometric-to-Binary-Computational-Bridge/fabrication/couplers.py`; the backfill entries are marked verbatim. | Already CC0 upstream. | Retained unchanged with upstream provenance; this history does not claim its upstream authorship. |
| `scenario_engine/physics/__init__.py`, `scenario_engine/physics/eigenmodes.py`, `scenario_engine/physics/pipe_modes.py` | Each identifies `JinnZ2/Geometric-to-Binary-Computational-Bridge/fabrication/` or the exact upstream source path. | Already CC0 upstream. | Retained unchanged with upstream provenance; this history does not claim its upstream authorship. |

Reachable commits list JinnZ2/Jinn2Z identities and `Claude <noreply@anthropic.com>`; no separate external contributor license notice was found outside the explicitly preserved upstream material above. A commit identity is provenance evidence, not a universal proof of authorship. Accordingly, this record does not claim to dedicate rights that the owner does not control.
