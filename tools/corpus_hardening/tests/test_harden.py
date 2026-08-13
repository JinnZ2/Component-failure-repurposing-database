"""Tests for tools/corpus_hardening/harden.py."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
HARDEN_PATH = HERE.parent / "harden.py"
TEMPLATE_DIR = HERE.parent / "templates"
EXAMPLE_CONFIG = HERE.parent / "configs" / "component-failure-repurposing-database.json"


def _load_harden_module():
    """Load harden.py as a module without requiring it to be packaged."""
    spec = importlib.util.spec_from_file_location("harden_under_test", HARDEN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harden = _load_harden_module()


def _minimal_cfg(**overrides) -> dict:
    base = {
        "repo_name": "example-repo",
        "github_owner": "JinnZ2",
        "domain": "example_domain",
        "purpose": "An example repository for unit tests.",
        "license": "CC0-1.0",
        "authors": [
            {"name": "Test Author", "family-names": "Author",
             "given-names": "Test", "affiliation": "JinnZ2 CC0 Foundation"},
        ],
    }
    base.update(overrides)
    return base


def _write_cfg(d: pathlib.Path, cfg: dict) -> pathlib.Path:
    p = d / "cfg.json"
    p.write_text(json.dumps(cfg))
    return p


class LoadConfigTests(unittest.TestCase):

    def test_minimal_config_loads(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write_cfg(pathlib.Path(td), _minimal_cfg())
            cfg = harden.load_config(p)
            self.assertEqual(cfg["repo_name"], "example-repo")
            self.assertEqual(cfg["methodology"], "falsifiable_claims_based")
            self.assertEqual(cfg["dependencies"], "stdlib_only")
            self.assertEqual(cfg["ci_python_versions"], ["3.10", "3.11", "3.12"])

    def test_missing_required_field_raises(self):
        with tempfile.TemporaryDirectory() as td:
            bad = _minimal_cfg()
            del bad["domain"]
            p = _write_cfg(pathlib.Path(td), bad)
            with self.assertRaises(ValueError) as ctx:
                harden.load_config(p)
            self.assertIn("domain", str(ctx.exception))

    def test_authors_must_have_name(self):
        with tempfile.TemporaryDirectory() as td:
            bad = _minimal_cfg(authors=[{"affiliation": "Anon"}])
            p = _write_cfg(pathlib.Path(td), bad)
            with self.assertRaises(ValueError):
                harden.load_config(p)

    def test_authors_must_be_nonempty(self):
        with tempfile.TemporaryDirectory() as td:
            bad = _minimal_cfg(authors=[])
            p = _write_cfg(pathlib.Path(td), bad)
            with self.assertRaises(ValueError):
                harden.load_config(p)


class RenderStringTests(unittest.TestCase):

    def test_simple_substitution(self):
        out = harden.render_string("Hi {{ repo_name }}!", {"repo_name": "X"})
        self.assertEqual(out, "Hi X!")

    def test_unknown_field_raises(self):
        with self.assertRaises(KeyError):
            harden.render_string("Hi {{ nope }}", {})

    def test_dotted_identifiers_pass_through(self):
        # GitHub Actions expressions like ${{ github.ref }} must not be
        # mistaken for our {{ field }} placeholders. The regex only
        # matches plain identifiers (no dots, no hyphens).
        template = "x: ${{ github.ref }} and ${{ matrix.python-version }}"
        out = harden.render_string(template, {})
        self.assertEqual(out, template)

    def test_rendered_lookup_wins(self):
        cfg = {"foo": "raw"}
        cfg["_rendered"] = {"foo": "pre-rendered"}
        out = harden.render_string("v={{ foo }}", cfg)
        self.assertEqual(out, "v=pre-rendered")


class PrepareCfgTests(unittest.TestCase):

    def test_ci_python_versions_rendered_as_yaml_flow(self):
        cfg = harden._prepare_cfg(_full_cfg())
        self.assertEqual(
            cfg["_rendered"]["ci_python_versions"],
            '["3.10", "3.11", "3.12"]',
        )

    def test_sister_repos_rendered_as_markdown_bullets(self):
        cfg = harden._prepare_cfg(_full_cfg(
            sister_repos=["https://a.example", "https://b.example"],
        ))
        self.assertEqual(
            cfg["_rendered"]["sister_repos"],
            "- https://a.example\n- https://b.example",
        )

    def test_empty_sister_repos_renders_placeholder(self):
        cfg = harden._prepare_cfg(_full_cfg(sister_repos=[]))
        self.assertIn("(none declared", cfg["_rendered"]["sister_repos"])

    def test_extra_glossary_rendered_as_table(self):
        cfg = harden._prepare_cfg(_full_cfg(
            extra_glossary={"Term": "Analogue"},
        ))
        table = cfg["_rendered"]["extra_glossary"]
        self.assertIn("| Term | Analogue |", table)
        self.assertIn("|---|---|", table)

    def test_claim_table_present_rendered_as_yes_no(self):
        c1 = harden._prepare_cfg(_full_cfg(claim_table_present=True))
        c2 = harden._prepare_cfg(_full_cfg(claim_table_present=False))
        self.assertEqual(c1["_rendered"]["claim_table_present"], "yes")
        self.assertEqual(c2["_rendered"]["claim_table_present"], "no")


def _full_cfg(**overrides) -> dict:
    """A config with all OPTIONAL_FIELDS defaults applied — mimics
    what load_config returns for tests of _prepare_cfg."""
    cfg = _minimal_cfg()
    for k, v in harden.OPTIONAL_FIELDS.items():
        cfg.setdefault(k, v if not isinstance(v, (list, dict)) else type(v)(v))
    cfg.update(overrides)
    return cfg


class BuildMetadataJsonTests(unittest.TestCase):

    def test_produces_valid_json_with_required_keys(self):
        cfg = _full_cfg()
        text = harden.build_metadata_json(cfg)
        parsed = json.loads(text)
        for k in ["name", "domain", "methodology", "dependencies",
                  "license", "falsifiability_level"]:
            self.assertIn(k, parsed)

    def test_repository_url_format(self):
        cfg = _full_cfg()
        parsed = json.loads(harden.build_metadata_json(cfg))
        self.assertEqual(
            parsed["repository"],
            "https://github.com/JinnZ2/example-repo",
        )


class BuildCitationCffTests(unittest.TestCase):

    def test_contains_required_top_level_keys(self):
        cfg = _full_cfg()
        text = harden.build_citation_cff(cfg)
        for key in ["cff-version:", "title:", "authors:", "license:",
                    "repository-code:", "keywords:"]:
            self.assertIn(key, text)

    def test_authors_emitted(self):
        cfg = _full_cfg(authors=[
            {"name": "A B", "family-names": "B", "given-names": "A",
             "affiliation": "Aff"},
        ])
        text = harden.build_citation_cff(cfg)
        self.assertIn("family-names: B", text)
        self.assertIn("given-names: A", text)
        self.assertIn('affiliation: "Aff"', text)

    def test_abstract_emitted_when_present(self):
        cfg = _full_cfg(abstract="An abstract.\nSecond line.")
        text = harden.build_citation_cff(cfg)
        self.assertIn("abstract: >", text)
        self.assertIn("An abstract.", text)


class HardenIntegrationTests(unittest.TestCase):

    def test_renders_all_artifacts_into_empty_target(self):
        cfg = _full_cfg()
        with tempfile.TemporaryDirectory() as td:
            target = pathlib.Path(td)
            results = harden.harden(cfg, TEMPLATE_DIR, target)
            written_paths = [
                "CITATION.cff",
                "metadata.json",
                "FALSIFIABILITY_NOTICE.txt",
                "GLOSSARY.md",
                "ARCHITECTURE.md",
                "README_HEADER.md",
                ".github/workflows/validate_claims.yml",
            ]
            for rel in written_paths:
                self.assertTrue(
                    (target / rel).exists(),
                    f"expected {rel} to be written",
                )
            for _, action, _ in results:
                self.assertEqual(action, "write")

    def test_metadata_json_is_valid_json(self):
        cfg = _full_cfg()
        with tempfile.TemporaryDirectory() as td:
            target = pathlib.Path(td)
            harden.harden(cfg, TEMPLATE_DIR, target)
            json.loads((target / "metadata.json").read_text())

    def test_validate_claims_yml_preserves_github_expressions(self):
        cfg = _full_cfg()
        with tempfile.TemporaryDirectory() as td:
            target = pathlib.Path(td)
            harden.harden(cfg, TEMPLATE_DIR, target)
            text = (target / ".github/workflows/validate_claims.yml").read_text()
            self.assertIn("${{ github.ref }}", text)
            self.assertIn("${{ matrix.python-version }}", text)

    def test_validate_claims_yml_renders_python_matrix(self):
        cfg = _full_cfg(ci_python_versions=["3.11", "3.12"])
        with tempfile.TemporaryDirectory() as td:
            target = pathlib.Path(td)
            harden.harden(cfg, TEMPLATE_DIR, target)
            text = (target / ".github/workflows/validate_claims.yml").read_text()
            self.assertIn('["3.11", "3.12"]', text)

    def test_dry_run_writes_nothing(self):
        cfg = _full_cfg()
        with tempfile.TemporaryDirectory() as td:
            target = pathlib.Path(td)
            results = harden.harden(cfg, TEMPLATE_DIR, target, dry_run=True)
            for _, action, _ in results:
                self.assertEqual(action, "dry-run")
            self.assertEqual(list(target.iterdir()), [])

    def test_skip_existing_then_force_overwrite(self):
        cfg = _full_cfg()
        with tempfile.TemporaryDirectory() as td:
            target = pathlib.Path(td)
            harden.harden(cfg, TEMPLATE_DIR, target)
            (target / "metadata.json").write_text("{}")
            r2 = harden.harden(cfg, TEMPLATE_DIR, target)
            actions = {a: act for a, act, _ in r2}
            self.assertEqual(actions["metadata.json"], "skip")

            r3 = harden.harden(cfg, TEMPLATE_DIR, target, force=True)
            actions3 = {a: act for a, act, _ in r3}
            self.assertEqual(actions3["metadata.json"], "replace")
            self.assertIn("example_domain",
                          (target / "metadata.json").read_text())


class ExampleConfigEndToEndTests(unittest.TestCase):
    """The shipped example config must round-trip cleanly."""

    def test_example_config_loads(self):
        cfg = harden.load_config(EXAMPLE_CONFIG)
        self.assertEqual(cfg["repo_name"], "Component-failure-repurposing-database")
        self.assertEqual(cfg["domain"], "substrate_calibration_framework")
        self.assertTrue(cfg["claim_table_present"])

    def test_example_config_renders_without_errors(self):
        cfg = harden.load_config(EXAMPLE_CONFIG)
        with tempfile.TemporaryDirectory() as td:
            target = pathlib.Path(td)
            harden.harden(cfg, TEMPLATE_DIR, target)
            self.assertTrue((target / "metadata.json").exists())
            parsed = json.loads((target / "metadata.json").read_text())
            self.assertEqual(parsed["domain"], "substrate_calibration_framework")
            self.assertIn("scenario_engine.runner", "\n".join(parsed["subsystems"]))


class StubConfigsValidateTests(unittest.TestCase):
    """Every shipped stub config must load. They contain TODO markers
    but should still pass schema validation so users can render and
    iterate."""

    def test_all_stub_configs_load(self):
        configs_dir = HERE.parent / "configs"
        seen = 0
        for cfg_path in configs_dir.glob("*.json"):
            if cfg_path.name.startswith("_"):
                continue
            harden.load_config(cfg_path)
            seen += 1
        self.assertGreater(seen, 1,
            "expected at least the example + one stub config")


if __name__ == "__main__":
    unittest.main()
