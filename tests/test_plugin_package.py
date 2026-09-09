from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "office-kit"
BUILD_PATH = ROOT / "scripts" / "plugin" / "build.py"
BOOTSTRAP_PATH = (
    PLUGIN / "skills" / "setup-office-kit" / "scripts" / "bootstrap.py"
)

# Importing a packaged script during tests must not contaminate the plugin with
# __pycache__; binary/generated payloads are deliberately forbidden.
sys.dont_write_bytecode = True


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build = load_module("officekit_plugin_build", BUILD_PATH)
bootstrap = load_module("officekit_plugin_bootstrap", BOOTSTRAP_PATH)


def capture_main(module, argv: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = module.main(argv)
    return int(code), buffer.getvalue()


class PluginManifestTests(unittest.TestCase):
    def test_portable_manifest_targets_agent_plugins_1(self) -> None:
        manifest = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["$schema"],
            "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        )
        self.assertEqual(manifest["name"], "office-kit")
        self.assertEqual(manifest["version"], build.VERSION)
        self.assertEqual(
            set(manifest),
            {
                "$schema",
                "name",
                "version",
                "description",
                "author",
                "homepage",
                "repository",
                "keywords",
            },
        )

    def test_client_adapters_match_portable_metadata(self) -> None:
        portable = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
        claude = json.loads(
            (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        codex = json.loads(
            (PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        for key in (
            "name",
            "version",
            "description",
            "author",
            "homepage",
            "repository",
        ):
            self.assertEqual(claude[key], portable[key])
            self.assertEqual(codex[key], portable[key])
        self.assertEqual(codex["skills"], "./skills/")

    def test_only_officekit_skills_are_packaged(self) -> None:
        skills = {
            path.parent.name
            for path in (PLUGIN / "skills").glob("*/SKILL.md")
            if path.is_file()
        }
        self.assertEqual(skills, set(build.SKILLS))
        for forbidden in (
            "slidev",
            "slidev-layouts",
            "slidev-themes",
            "hyperframes",
            "hyperframes-core",
            "hyperframes-cli",
            "html",
            "capabilities-manager",
        ):
            self.assertNotIn(forbidden, skills)

    def test_skills_conform_to_agent_skills_frontmatter(self) -> None:
        for skill_dir in sorted((PLUGIN / "skills").iterdir()):
            skill = skill_dir / "SKILL.md"
            if not skill.is_file():
                continue
            text = skill.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), skill)
            _, raw, body = text.split("---", 2)
            frontmatter = yaml.safe_load(raw)
            self.assertIsInstance(frontmatter, dict, skill)
            self.assertEqual(frontmatter["name"], skill_dir.name, skill)
            self.assertTrue(frontmatter["description"].strip(), skill)
            self.assertLessEqual(len(frontmatter["name"]), 64, skill)
            self.assertLessEqual(len(frontmatter["description"]), 1024, skill)
            self.assertTrue(body.strip(), skill)

    def test_external_components_and_binary_payloads_are_absent(self) -> None:
        self.assertFalse((PLUGIN / "mcp.json").exists())
        for name in ("agents", "hooks", "node_modules", ".venv"):
            self.assertFalse((PLUGIN / name).exists(), name)
        self.assertFalse((PLUGIN / "capabilities.yaml").exists())
        all_files = [path for path in PLUGIN.rglob("*") if path.is_file()]
        self.assertFalse(any(path.is_symlink() for path in PLUGIN.rglob("*")))
        self.assertTrue(
            all("evals" in path.relative_to(PLUGIN).parts for path in all_files if path.suffix == ".wav")
        )
        payload_brands = (
            PLUGIN
            / "skills"
            / "setup-office-kit"
            / "assets"
            / "workspace"
            / "brands"
        )
        self.assertEqual(
            {path.name for path in payload_brands.iterdir() if path.is_dir()},
            {"officekit"},
        )
        self.assertFalse(any(path.name in {"uv.lock", "package-lock.json"} for path in all_files))

    def test_build_check_passes(self) -> None:
        code, output = capture_main(build, ["--check"])
        self.assertEqual(code, 0, output)
        self.assertIn("allowlist match", output)

    def test_generated_payload_matches_canonical_runtime(self) -> None:
        payload = (
            PLUGIN
            / "skills"
            / "setup-office-kit"
            / "assets"
            / "workspace"
        )
        for relative in build.WORKSPACE_FILES:
            self.assertEqual(
                (payload / relative).read_bytes(),
                (ROOT / relative).read_bytes(),
                relative,
            )
        portable_workflow = (
            ROOT / "scripts" / "plugin" / "WORKFLOW.md"
        ).read_bytes()
        for name in ("WORKFLOW.md", "AGENTS.md", "CLAUDE.md"):
            self.assertEqual((payload / name).read_bytes(), portable_workflow)

    def test_repo_skills_directory_links_to_plugin_canonical_source(self) -> None:
        legacy = ROOT / "skills"
        canonical = PLUGIN / "skills"
        self.assertTrue(legacy.is_symlink(), legacy)
        self.assertEqual(legacy.resolve(), canonical.resolve())
        for name in build.SKILLS:
            self.assertTrue((legacy / name / "SKILL.md").is_file(), name)


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.host = Path(self.temp.name)
        self.target = self.host / "office-kit"

    def install(self, *extra: str) -> tuple[int, str]:
        return capture_main(
            bootstrap,
            ["--target", str(self.target), "--no-install", *extra],
        )

    def test_bootstrap_is_idempotent(self) -> None:
        code, output = self.install()
        self.assertEqual(code, 0, output)
        self.assertTrue((self.target / ".officekit-managed.json").is_file())
        self.assertTrue((self.target / "projects" / ".gitkeep").is_file())
        self.assertTrue((self.target / "scripts" / "document" / "doc.py").is_file())
        self.assertFalse((self.target / "node_modules").exists())

        code, output = self.install()
        self.assertEqual(code, 0, output)
        self.assertIn("0 changed", output)

    def test_bootstrap_refuses_unrelated_nonempty_target(self) -> None:
        self.target.mkdir()
        (self.target / "keep.txt").write_text("mine\n", encoding="utf-8")
        code, output = self.install()
        self.assertEqual(code, 2)
        self.assertIn("non-empty", output)
        self.assertEqual(
            (self.target / "keep.txt").read_text(encoding="utf-8"),
            "mine\n",
        )

    def test_upgrade_refuses_modified_managed_file(self) -> None:
        self.assertEqual(self.install()[0], 0)
        config = self.target / "config.toml"
        config.write_text("user change\n", encoding="utf-8")
        code, output = self.install()
        self.assertEqual(code, 2)
        self.assertIn("modified after installation", output)
        self.assertEqual(config.read_text(encoding="utf-8"), "user change\n")

        unrelated = self.target / "keep.txt"
        unrelated.write_text("preserve\n", encoding="utf-8")
        code, output = self.install("--force")
        self.assertEqual(code, 0, output)
        self.assertIn("[brand]", config.read_text(encoding="utf-8"))
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "preserve\n")

    def test_bootstrapped_document_and_deck_smoke(self) -> None:
        self.assertEqual(self.install()[0], 0)

        doc = self._run(
            "scripts/document/doc.py",
            "new",
            "memo",
            "--title",
            "Plugin Smoke",
        )
        self.assertEqual(doc.returncode, 0, doc.stdout + doc.stderr)
        html = self.target / "projects" / "memo" / "memo.html"
        text = html.read_text(encoding="utf-8")
        text = text.replace(
            "<!-- officekit:content -->",
            """
      <section id="summary" aria-labelledby="summary-heading">
        <h2 id="summary-heading">Summary</h2>
        <p class="lede">Portable plugin smoke test.</p>
      </section>
            """.strip(),
        )
        html.write_text(text, encoding="utf-8")
        self.assertEqual(
            self._run("scripts/document/doc.py", "toc", str(html)).returncode,
            0,
        )
        checked = self._run("scripts/document/doc.py", "check", str(html))
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

        deck = self._run(
            "scripts/presentation/deck.py",
            "new",
            "smoke-deck",
            "--title",
            "Plugin Smoke",
            "--no-install",
        )
        self.assertEqual(deck.returncode, 0, deck.stdout + deck.stderr)
        self._fake_slide_dependencies()
        audited = self._run(
            "scripts/presentation/deck.py",
            "audit",
            "smoke-deck",
        )
        self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)

    def _run(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, script, *args],
            cwd=self.target,
            text=True,
            capture_output=True,
            check=False,
        )

    def _fake_slide_dependencies(self) -> None:
        layouts = (
            self.target / "node_modules" / "@slidev" / "client" / "layouts"
        )
        layouts.mkdir(parents=True)
        for name in (
            "center",
            "cover",
            "default",
            "end",
            "fact",
            "image-right",
            "quote",
            "section",
            "statement",
            "two-cols",
            "two-cols-header",
        ):
            (layouts / f"{name}.vue").write_text("<template />\n", encoding="utf-8")

        icons = (
            self.target
            / "node_modules"
            / "@iconify-json"
            / "lucide"
            / "icons.json"
        )
        icons.parent.mkdir(parents=True)
        slide_text = (
            self.target / "projects" / "smoke-deck" / "slides.md"
        ).read_text(encoding="utf-8")
        import re

        names = sorted(set(re.findall(r"<lucide-([a-z0-9-]+)", slide_text)))
        icons.write_text(
            json.dumps({"icons": {name: {} for name in names}}),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
