# `tools/corpus_hardening/`

Reusable generator for the canonical corpus-hardening artifact set:

- `CITATION.cff` — machine-readable citation
- `metadata.json` — structured semantic metadata
- `FALSIFIABILITY_NOTICE.txt` — audit-trail statement
- `GLOSSARY.md` — substrate-primary ↔ academic bridge vocabulary
- `ARCHITECTURE.md` — subsystem map and constraints
- `README_HEADER.md` — header block to merge into the target README
- `.github/workflows/validate_claims.yml` — CI: stdlib unittest +
  metadata sanity checks

The generator is stdlib-only Python (matches the corpus-wide
constraint). Templates use simple `{{ field }}` placeholder
substitution; no Jinja, no PyYAML, no external deps.

## Layout

```
tools/corpus_hardening/
├── harden.py                 # the executable
├── README.md                 # this file
├── templates/                # *.template files with {{ field }} placeholders
│   ├── FALSIFIABILITY_NOTICE.txt.template
│   ├── GLOSSARY.md.template
│   ├── ARCHITECTURE.md.template
│   ├── README_HEADER.md.template
│   └── validate_claims.yml.template
├── configs/                  # per-repo JSON configs
│   ├── _schema.md                                  # field documentation
│   ├── _STUB_TEMPLATE.json                         # copy-and-fill starting point
│   ├── component-failure-repurposing-database.json # fully populated example
│   └── <13 sister-repo stub configs>               # seeded from PROJECTS.md
└── tests/                    # stdlib unittest cases
    └── test_harden.py
```

## Usage

### One-shot: harden a target repo

```bash
python3 tools/corpus_hardening/harden.py \
    --config tools/corpus_hardening/configs/component-failure-repurposing-database.json \
    --out .

# or on a sibling repo
python3 tools/corpus_hardening/harden.py \
    --config tools/corpus_hardening/configs/ai-human-audit-protocol.json \
    --out ../ai-human-audit-protocol
```

### Safety flags

| Flag | Meaning |
|---|---|
| (default) | Skip files that already exist; warn at the end |
| `--force` | Overwrite existing files |
| `--dry-run` | Print actions without writing |

### Adding a new repo

1. Copy `configs/_STUB_TEMPLATE.json` to `configs/<slug>.json`.
2. Fill in `repo_name`, `domain`, `purpose`, and any subsystem /
   sister-repo lists. The other fields fall back to sensible defaults
   for the JinnZ2 CC0 corpus (stdlib-only, falsifiable, etc.).
3. Run `harden.py` against the target repo path.
4. Manually reconcile `README_HEADER.md` into the target's `README.md`.
5. On GitHub, add the topics listed in `metadata.json["github_topics"]`
   via the repository settings (no API access from this script).

### Refreshing artifacts after a config change

```bash
python3 tools/corpus_hardening/harden.py \
    --config configs/<slug>.json --out <target> --force
```

`--force` overwrites; `--dry-run` previews first.

## Tests

```bash
python3 -m unittest discover tools/corpus_hardening/tests -v
```

Tests use a temp directory and verify:

- Required fields are enforced (missing fields raise `ValueError`)
- Templates render to valid `metadata.json` (JSON), valid
  `CITATION.cff` (round-trip key check), and valid YAML headers
- `--dry-run` writes nothing
- Default mode skips existing files
- `--force` overwrites existing files
- The renderer leaves GitHub Actions `${{ github.ref }}` expressions
  alone (placeholder regex doesn't match dotted identifiers)

## Design notes

- **No template engine.** A 4-line regex substitution is enough. Adding
  a dependency just to render seven files would violate the stdlib-only
  constraint the script is itself trying to encourage.
- **Lists are pre-rendered per context.** YAML matrix entries need flow
  syntax; markdown sister-repo lists need bullet syntax. `_prepare_cfg`
  produces both forms before substitution.
- **JSON / YAML files are built programmatically**, not via string
  templates. That keeps the output syntactically valid by construction.
- **No GitHub API calls.** The script writes files; setting topics and
  enabling branch protection are out of scope.
