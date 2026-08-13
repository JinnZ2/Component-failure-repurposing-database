# Config schema

Each `configs/<name>.json` describes one repository for the corpus
hardening generator (`harden.py`). The script validates required fields
on load and fails loudly on missing keys.

## Required fields

| Field | Type | Notes |
|---|---|---|
| `repo_name` | string | The GitHub repository name (case-sensitive) |
| `github_owner` | string | The GitHub user/org owning the repo |
| `domain` | string | Substrate-primary domain label, snake_case |
| `purpose` | string | 2–3 sentence statement of what the repo does |
| `license` | string | SPDX identifier (e.g. `CC0-1.0`, `MIT`, `Apache-2.0`) |
| `authors` | list of {name, family-names?, given-names?, affiliation?} | At least one |

## Optional fields (with defaults)

| Field | Default | Notes |
|---|---|---|
| `methodology` | `falsifiable_claims_based` | |
| `dependencies` | `stdlib_only` | |
| `falsifiability_level` | `high` | `high` / `medium` / `low` |
| `claim_table_present` | `false` | Set true if the repo has a claim table |
| `claim_table_paths` | `[]` | Paths to claim tables (CSV / JSON) |
| `subsystems` | `[]` | Bullet list strings for ARCHITECTURE.md |
| `sister_repos` | `[]` | Bullet list strings for ARCHITECTURE.md |
| `github_topics` | `[]` | Topics to set on GitHub (manual step) |
| `extra_glossary` | `{}` | Dict of substrate→academic mappings unique to this repo |
| `extra_keywords` | `[]` | Extra CITATION.cff keywords |
| `test_command` | `python3 -m unittest discover -v` | CI command |
| `ci_python_versions` | `["3.10", "3.11", "3.12"]` | Matrix for CI |
| `abstract` | `""` | CITATION.cff abstract |
| `readme_overview` | `""` | Body paragraphs for README_HEADER.md |
| `readme_quickstart` | `""` | Quickstart block for README_HEADER.md |
| `readme_layout` | `""` | Repository layout block for README_HEADER.md |

## Example

See `component-failure-repurposing-database.json` for a fully populated
example used to render the artifacts in this repository.
