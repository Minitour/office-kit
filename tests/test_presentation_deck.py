from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "presentation" / "deck.py"
SPEC = importlib.util.spec_from_file_location("presentation_deck", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
deck = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = deck
SPEC.loader.exec_module(deck)


def run(*argv: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = deck.main(list(argv))
    return code, buffer.getvalue()


class DeckScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        shutil.copytree(ROOT / "brands" / "officekit", self.root / "brands" / "officekit")
        shutil.copytree(ROOT / ".templates" / "presentation", self.root / ".templates" / "presentation")
        shutil.copy(ROOT / "config.toml", self.root / "config.toml")

    def test_new_renders_jinja_and_binds_the_default_brand(self) -> None:
        code, output = run(
            "new",
            "kickoff",
            "--title",
            "Q3 Kickoff",
            "--workspace-root",
            str(self.root),
        )
        self.assertEqual(code, 0, output)
        dest = self.root / "projects" / "kickoff"
        style = (dest / "style.css").read_text(encoding="utf-8")
        slides = (dest / "slides.md").read_text(encoding="utf-8")
        package = (dest / "package.json").read_text(encoding="utf-8")
        self.assertIn("../../brands/officekit/tokens.css", style)
        self.assertIn("../../brands/officekit/assets/logo.svg", style)
        self.assertNotIn("{{", style)
        self.assertIn("title: Q3 Kickoff", slides)
        self.assertIn("theme: default", slides)
        self.assertIn("aspectRatio: \"16/9\"", slides)
        self.assertIn("slidev --port 3030", package)
        self.assertFalse((dest / "style.css.j2").exists())
        self.assertIn("npm install -w projects/kickoff", output)

    def test_new_can_bind_a_named_brand(self) -> None:
        other = self.root / "brands" / "acme"
        shutil.copytree(self.root / "brands" / "officekit", other)
        code, output = run(
            "new",
            "acme-pitch",
            "--brand",
            "acme",
            "--workspace-root",
            str(self.root),
        )
        self.assertEqual(code, 0, output)
        style = (self.root / "projects" / "acme-pitch" / "style.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("../../brands/acme/tokens.css", style)

    def test_refuses_to_clobber_an_existing_project(self) -> None:
        run("new", "kickoff", "--workspace-root", str(self.root))
        code, output = run("new", "kickoff", "--workspace-root", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("already exists", output)
        code, output = run(
            "new", "kickoff", "--force", "--title", "Retitled", "--workspace-root", str(self.root)
        )
        self.assertEqual(code, 0, output)
        self.assertIn("title: Retitled", (self.root / "projects" / "kickoff" / "slides.md").read_text())


if __name__ == "__main__":
    unittest.main()
