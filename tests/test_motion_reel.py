from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "motion" / "reel.py"
SPEC = importlib.util.spec_from_file_location("motion_reel", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
reel = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reel
SPEC.loader.exec_module(reel)

SKILL = ROOT / "plugins" / "office-kit" / "skills" / "create-motion-reel"


def run(*argv: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = reel.main(list(argv))
    return code, buffer.getvalue()


class MotionReelScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        shutil.copytree(ROOT / "brands" / "officekit", self.root / "brands" / "officekit")
        shutil.copytree(ROOT / ".templates" / "motion", self.root / ".templates" / "motion")
        shutil.copy(ROOT / "config.toml", self.root / "config.toml")

    def new(self, *extra: str) -> tuple[int, str]:
        return run("new", "launch", "--no-install", "--workspace-root", str(self.root), *extra)

    def test_new_renders_jinja_and_snapshots_the_brand(self) -> None:
        code, output = self.new("--title", "Launch reel", "--duration", "10")
        self.assertEqual(code, 0, output)
        dest = self.root / "projects" / "launch"
        timeline = (dest / "timeline.js").read_text(encoding="utf-8")
        self.assertIn('title: "Launch reel"', timeline)
        self.assertIn('name: "OfficeKit"', timeline)
        self.assertIn('logo: "brand/assets/logo.svg"', timeline)
        self.assertIn("width: 1920", timeline)
        self.assertIn("fps: 60", timeline)
        self.assertIn("duration: 10.0", timeline)
        self.assertNotIn("{{", timeline)
        package = json.loads((dest / "package.json").read_text(encoding="utf-8"))
        self.assertIn("playwright-chromium", package["dependencies"])
        self.assertTrue((dest / "brand" / "tokens.css").is_file())
        self.assertTrue((dest / "brand" / "assets" / "logo.svg").is_file())
        self.assertTrue((dest / "plan").is_dir())
        self.assertFalse((dest / "timeline.js.j2").exists())
        self.assertIn("reel.py stills launch", output)

    def test_page_reads_brand_tokens_instead_of_literals(self) -> None:
        self.assertEqual(self.new()[0], 0)
        html = (self.root / "projects" / "launch" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="./brand/tokens.css"', html)
        self.assertIn("--color-primary", html)
        self.assertIn("--font-heading", html)
        self.assertIsNone(reel.IMPURE.search(html))

    def test_refresh_rewrites_a_drifted_snapshot(self) -> None:
        self.assertEqual(self.new()[0], 0)
        tokens = self.root / "projects" / "launch" / "brand" / "tokens.css"
        tokens.write_text("/* stale */\n", encoding="utf-8")
        code, output = run("refresh", "launch", "--workspace-root", str(self.root))
        self.assertEqual(code, 0, output)
        self.assertEqual(
            tokens.read_text(encoding="utf-8"),
            (self.root / "brands" / "officekit" / "tokens.css").read_text(encoding="utf-8"),
        )

    def test_unknown_brand_is_rejected(self) -> None:
        code, output = self.new("--brand", "nope")
        self.assertEqual(code, 2)
        self.assertIn("nope", output)

    def test_existing_project_needs_force(self) -> None:
        self.assertEqual(self.new()[0], 0)
        code, output = self.new()
        self.assertEqual(code, 2)
        self.assertIn("--force", output)
        self.assertEqual(self.new("--force")[0], 0)

    def test_static_audit_flags_clocks_and_em_dashes(self) -> None:
        self.assertEqual(self.new()[0], 0)
        code, output = run(
            "audit", "launch", "--skip-render", "--workspace-root", str(self.root)
        )
        self.assertEqual(code, 0, output)
        page = self.root / "projects" / "launch" / "index.html"
        text = page.read_text(encoding="utf-8")
        page.write_text(
            text.replace("function seek(t) {", "function seek(t) {\n  t += Math.random();")
            .replace("'The payoff.'", "'The payoff \u2014 now.'"),
            encoding="utf-8",
        )
        code, output = run(
            "audit", "launch", "--skip-render", "--workspace-root", str(self.root)
        )
        self.assertEqual(code, 1, output)
        self.assertIn("Math.random", output)
        self.assertIn("em dash", output)


class MotionReelSkillTests(unittest.TestCase):
    def test_skill_positions_itself_against_create_video(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: create-motion-reel", text)
        self.assertIn("create-video", text)
        self.assertIn("scripts/motion/reel.py", text)
        self.assertIn("plan/PLAN.md", text)
        self.assertIn("Render only when the user names", text)
        self.assertNotIn("\u2014", text)

    def test_evals_parse(self) -> None:
        data = json.loads((SKILL / "evals" / "evals.json").read_text(encoding="utf-8"))
        self.assertEqual(data["skill_name"], "create-motion-reel")
        self.assertTrue(all(e["expectations"] for e in data["evals"]))


if __name__ == "__main__":
    unittest.main()
