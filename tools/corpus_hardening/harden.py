#!/usr/bin/env python3
"""
Corpus hardening artifact generator.

Reads a per-repo JSON config and renders the canonical set of corpus-
friendly artifacts into a target directory:

    CITATION.cff
    metadata.json
    FALSIFIABILITY_NOTICE.txt
    GLOSSARY.md
    ARCHITECTURE.md
    README_HEADER.md     (a header block to prepend / merge into README.md)
    .github/workflows/validate_claims.yml

The script is intentionally stdlib-only (matches the corpus-wide
constraint) and uses simple ``{{ field }}`` placeholder substitution
rather than a real template engine, so it works on any Python 3.8+
interpreter without dependencies.

Usage::

    python3 -m tools.corpus_hardening.harden \\
        --config tools/corpus_hardening/configs/<name>.json \\
        --out /path/to/target/repo

    # or, render into a sibling repo using an absolute target path
    python3 tools/corpus_hardening/harden.py \\
        --config tools/corpus_hardening/configs/myrepo.json \\
        --out ../myrepo \\
        --dry-run         # preview without writing

Config schema is documented in ``configs/_schema.md`` and validated at
load time. Missing required fields fail loudly.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
from typing import Any


REQUIRED_FIELDS = (
    "repo_name",
    "github_owner",
    "domain",
    "purpose",
    "license",
    "authors",
)

OPTIONAL_FIELDS = {
    "methodology": "falsifiable_claims_based",
    "dependencies": "stdlib_only",
    "falsifiability_level": "high",
    "claim_table_present": False,
    "claim_table_paths": [],
    "subsystems": [],
    "sister_repos": [],
    "github_topics": [],
    "extra_glossary": {},
    "extra_keywords": [],
    "test_command": "python3 -m unittest discover -v",
    "ci_python_versions": ["3.10", "3.11", "3.12"],
    "abstract": "",
    "readme_overview": "",
    "readme_quickstart": "",
    "readme_layout": "",
}


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def load_config(path: pathlib.Path) -> dict:
    """Load and validate a per-repo config from JSON."""
    with path.open() as f:
        cfg = json.load(f)

    if not isinstance(cfg, dict):
        raise ValueError(f"{path}: top-level must be a JSON object")

    missing = [k for k in REQUIRED_FIELDS if k not in cfg]
    if missing:
        raise ValueError(f"{path}: missing required fields: {missing}")

    for k, default in OPTIONAL_FIELDS.items():
        cfg.setdefault(k, default)

    if not isinstance(cfg["authors"], list) or not cfg["authors"]:
        raise ValueError(f"{path}: 'authors' must be a non-empty list")
    for author in cfg["authors"]:
        if "name" not in author:
            raise ValueError(f"{path}: each author needs a 'name' field")

    return cfg


def render_string(template: str, cfg: dict) -> str:
    """Substitute {{ field }} placeholders from cfg.

    Lookup falls back to ``cfg['_rendered'][key]`` for keys that were
    pre-rendered (e.g. lists formatted as markdown bullets, YAML flow
    sequences, etc.) by ``_prepare_cfg``.
    """

    def replace(match: re.Match) -> str:
        key = match.group(1)
        rendered = cfg.get("_rendered", {})
        if key in rendered:
            return rendered[key]
        if key not in cfg:
            raise KeyError(
                f"template references unknown field {{{{ {key} }}}}; "
                f"add it to the config or to OPTIONAL_FIELDS defaults"
            )
        return _stringify(cfg[key])

    return _PLACEHOLDER_RE.sub(replace, template)


def _prepare_cfg(cfg: dict) -> dict:
    """Pre-render values that need context-specific formatting.

    Returns a shallow copy of cfg with a ``_rendered`` sub-dict
    containing string-formatted versions of list/dict fields.
    """
    out = dict(cfg)
    rendered = {}

    versions = cfg["ci_python_versions"]
    rendered["ci_python_versions"] = (
        "[" + ", ".join(f'"{v}"' for v in versions) + "]"
    )

    sisters = cfg["sister_repos"]
    if sisters:
        rendered["sister_repos"] = "\n".join(f"- {s}" for s in sisters)
    else:
        rendered["sister_repos"] = "*(none declared yet)*"

    subs = cfg["subsystems"]
    if subs:
        rendered["subsystems"] = "\n".join(f"- {s}" for s in subs)
    else:
        rendered["subsystems"] = "*(none declared yet)*"

    glossary = cfg.get("extra_glossary", {})
    if isinstance(glossary, dict) and glossary:
        lines = ["| Substrate-primary term | Academic / industry analogue |",
                 "|---|---|"]
        for k, v in glossary.items():
            lines.append(f"| {k} | {v} |")
        rendered["extra_glossary"] = "\n".join(lines)
    else:
        rendered["extra_glossary"] = (
            "*(No repository-specific glossary entries yet — add them here.)*"
        )

    rendered["claim_table_present"] = "yes" if cfg["claim_table_present"] else "no"

    out["_rendered"] = rendered
    return out


def _stringify(value: Any) -> str:
    """Render a config value for use in a template."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(_stringify(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, indent=2, sort_keys=True)
    if value is None:
        return ""
    return str(value)


def render_template_file(template_path: pathlib.Path, cfg: dict) -> str:
    return render_string(template_path.read_text(), cfg)


def build_metadata_json(cfg: dict) -> str:
    """metadata.json is structured, so build it from the config directly
    rather than substituting into a textual template — that way we
    cannot produce invalid JSON."""
    payload = {
        "name": cfg["repo_name"],
        "repository": f"https://github.com/{cfg['github_owner']}/{cfg['repo_name']}",
        "domain": cfg["domain"],
        "methodology": cfg["methodology"],
        "dependencies": cfg["dependencies"],
        "license": cfg["license"],
        "corpus_target": True,
        "falsifiability_level": cfg["falsifiability_level"],
        "claim_table_present": cfg["claim_table_present"],
        "claim_table_paths": cfg["claim_table_paths"],
        "subsystems": cfg["subsystems"],
        "purpose": cfg["purpose"],
        "sister_repos": cfg["sister_repos"],
        "github_topics": cfg["github_topics"],
        "authors": cfg["authors"],
    }
    return json.dumps(payload, indent=2) + "\n"


def build_citation_cff(cfg: dict) -> str:
    """CITATION.cff is YAML-like; build it explicitly to keep formatting
    predictable and to avoid pulling in a YAML library."""
    lines = [
        "cff-version: 1.2.0",
        f'title: "{cfg["repo_name"]}"',
        'message: "If you use this software, please cite it using these metadata."',
        "authors:",
    ]
    for author in cfg["authors"]:
        if "family-names" in author and "given-names" in author:
            lines.append(f'  - family-names: {author["family-names"]}')
            lines.append(f'    given-names: {author["given-names"]}')
        elif "family-names" in author:
            lines.append(f'  - family-names: "{author["family-names"]}"')
        else:
            lines.append(f'  - name: "{author["name"]}"')
        if "affiliation" in author:
            lines.append(f'    affiliation: "{author["affiliation"]}"')
    lines.append(f'license: {cfg["license"]}')
    lines.append(
        f'repository-code: "https://github.com/{cfg["github_owner"]}/{cfg["repo_name"]}"'
    )
    if cfg["abstract"]:
        lines.append("abstract: >")
        for ln in cfg["abstract"].strip().splitlines():
            lines.append(f"  {ln.strip()}")
    base_keywords = [
        "public-domain" if cfg["license"].lower().startswith("cc0") else cfg["license"].lower(),
        "falsifiable",
        cfg["dependencies"].replace("_", "-"),
        cfg["domain"].replace("_", "-"),
    ]
    keywords = base_keywords + list(cfg.get("extra_keywords", []))
    seen = set()
    deduped = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    lines.append("keywords:")
    for k in deduped:
        lines.append(f"  - {k}")
    return "\n".join(lines) + "\n"


def write_file(
    target_root: pathlib.Path,
    relative: str,
    content: str,
    *,
    dry_run: bool,
    force: bool,
) -> tuple[str, str]:
    """Write content to target_root/relative.

    Returns (action, path) where action is one of:
      'write'    — new file written
      'skip'     — file existed and force=False
      'replace'  — existing file overwritten because force=True
      'dry-run'  — would have written; no change made
    """
    dest = target_root / relative
    exists = dest.exists()

    if dry_run:
        return ("dry-run", str(dest))

    if exists and not force:
        return ("skip", str(dest))

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content)
    return ("replace" if exists else "write", str(dest))


def harden(
    cfg: dict,
    template_dir: pathlib.Path,
    target_root: pathlib.Path,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> list[tuple[str, str, str]]:
    """Render all artifacts. Returns a list of (artifact, action, path)."""

    cfg = _prepare_cfg(cfg)
    plan: list[tuple[str, str]] = [
        ("CITATION.cff", build_citation_cff(cfg)),
        ("metadata.json", build_metadata_json(cfg)),
        ("FALSIFIABILITY_NOTICE.txt", render_template_file(
            template_dir / "FALSIFIABILITY_NOTICE.txt.template", cfg)),
        ("GLOSSARY.md", render_template_file(
            template_dir / "GLOSSARY.md.template", cfg)),
        ("ARCHITECTURE.md", render_template_file(
            template_dir / "ARCHITECTURE.md.template", cfg)),
        ("README_HEADER.md", render_template_file(
            template_dir / "README_HEADER.md.template", cfg)),
        (".github/workflows/validate_claims.yml", render_template_file(
            template_dir / "validate_claims.yml.template", cfg)),
    ]

    results: list[tuple[str, str, str]] = []
    for relative, content in plan:
        action, path = write_file(
            target_root, relative, content,
            dry_run=dry_run, force=force,
        )
        results.append((relative, action, path))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render corpus-hardening artifacts for a repo from a JSON config.",
    )
    parser.add_argument(
        "--config", required=True, type=pathlib.Path,
        help="Path to per-repo JSON config",
    )
    parser.add_argument(
        "--out", required=True, type=pathlib.Path,
        help="Target repo root directory",
    )
    parser.add_argument(
        "--templates", type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parent / "templates",
        help="Override template directory",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing files",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print actions without writing",
    )
    args = parser.parse_args(argv)

    if not args.config.exists():
        print(f"config not found: {args.config}", file=sys.stderr)
        return 2
    if not args.templates.exists():
        print(f"templates dir not found: {args.templates}", file=sys.stderr)
        return 2
    if not args.out.exists():
        print(f"target dir not found: {args.out}", file=sys.stderr)
        return 2

    cfg = load_config(args.config)
    results = harden(
        cfg, args.templates, args.out,
        dry_run=args.dry_run, force=args.force,
    )
    width = max(len(a) for a, _, _ in results)
    for artifact, action, path in results:
        print(f"  [{action:>7s}] {artifact.ljust(width)}  -> {path}")
    skipped = [r for r in results if r[1] == "skip"]
    if skipped and not args.force:
        print(
            f"\n{len(skipped)} file(s) skipped (already exist). "
            f"Pass --force to overwrite.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
