from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "brand" / "generate.py"
SPEC = importlib.util.spec_from_file_location("brand_generate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
generate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generate
SPEC.loader.exec_module(generate)


class BrandGenerateTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        source = ROOT / "brands" / "officekit"
        dest = self.root / "brands" / "officekit"
        shutil.copytree(source, dest)

    def test_check_passes_on_current_derivatives(self) -> None:
        self.assertEqual(
            generate.main(["--brand-dir", str(self.root / "brands" / "officekit"), "--check"]),
            0,
        )

    def test_regenerate_rewrites_stale_derivatives(self) -> None:
        tokens = self.root / "brands" / "officekit" / "tokens.css"
        tokens.write_text("/* stale */\n", encoding="utf-8")
        self.assertEqual(
            generate.main(["--brand-dir", str(self.root / "brands" / "officekit"), "--check"]),
            1,
        )
        self.assertEqual(
            generate.main(["--brand-dir", str(self.root / "brands" / "officekit")]),
            0,
        )
        self.assertEqual(
            generate.main(["--brand-dir", str(self.root / "brands" / "officekit"), "--check"]),
            0,
        )
        self.assertIn("--color-primary:", tokens.read_text(encoding="utf-8"))
        self.assertIn("brands/officekit/brand.json", tokens.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
