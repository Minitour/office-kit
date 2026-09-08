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
MODULE_PATH = ROOT / "scripts" / "video" / "video.py"
SPEC = importlib.util.spec_from_file_location("video_video", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
video = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = video
SPEC.loader.exec_module(video)


def run(*argv: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = video.main(list(argv))
    return code, buffer.getvalue()


class VideoScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        shutil.copytree(ROOT / "brands" / "officekit", self.root / "brands" / "officekit")
        shutil.copytree(ROOT / ".templates" / "video", self.root / ".templates" / "video")
        shutil.copy(ROOT / "config.toml", self.root / "config.toml")

    def test_new_renders_jinja_and_snapshots_the_brand(self) -> None:
        code, output = run(
            "new",
            "explainer",
            "--title",
            "Product tour",
            "--no-install",
            "--workspace-root",
            str(self.root),
        )
        self.assertEqual(code, 0, output)
        dest = self.root / "projects" / "explainer"
        html = (dest / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>Product tour</title>", html)
        self.assertIn('href="./brand/tokens.css"', html)
        self.assertIn('data-width="1920"', html)
        self.assertIn('data-height="1080"', html)
        self.assertIn('data-fps="30"', html)
        self.assertNotIn("{{", html)
        self.assertTrue((dest / "brand" / "tokens.css").is_file())
        self.assertTrue((dest / "brand" / "frame.md").is_file())
        self.assertTrue((dest / "brand" / "assets" / "logo.svg").is_file())
        self.assertFalse((dest / "index.html.j2").exists())
        self.assertIn("video.py dev explainer", output)

    def test_refresh_rewrites_a_drifted_snapshot(self) -> None:
        self.assertEqual(
            run(
                "new",
                "explainer",
                "--no-install",
                "--workspace-root",
                str(self.root),
            )[0],
            0,
        )
        tokens = self.root / "projects" / "explainer" / "brand" / "tokens.css"
        tokens.write_text("/* stale */\n", encoding="utf-8")
        code, output = run(
            "refresh",
            "explainer",
            "--workspace-root",
            str(self.root),
        )
        self.assertEqual(code, 0, output)
        self.assertIn("--color-primary:", tokens.read_text(encoding="utf-8"))
        self.assertIn("brands/officekit", output)

    def test_rejects_an_unknown_brand(self) -> None:
        code, output = run(
            "new",
            "explainer",
            "--brand",
            "missing",
            "--no-install",
            "--workspace-root",
            str(self.root),
        )
        self.assertEqual(code, 2)
        self.assertIn("does not exist", output)


if __name__ == "__main__":
    unittest.main()
