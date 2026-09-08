from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "brand" / "catalog.py"
SPEC = importlib.util.spec_from_file_location("brand_catalog", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
catalog = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = catalog
SPEC.loader.exec_module(catalog)


class BrandCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def write_brand(self, brand_id: str) -> Path:
        path = self.root / "brands" / brand_id
        path.mkdir(parents=True)
        (path / "brand.json").write_text("{}", encoding="utf-8")
        return path

    def test_lists_only_directories_that_hold_brand_json(self) -> None:
        self.write_brand("officekit")
        self.write_brand("acme")
        (self.root / "brands" / "notes.txt").write_text("x", encoding="utf-8")
        (self.root / "brands" / "Not-Valid").mkdir()
        (self.root / "brands" / "Not-Valid" / "brand.json").write_text("{}", encoding="utf-8")
        self.assertEqual(catalog.list_brand_ids(self.root), ["acme", "officekit"])

    def test_single_brand_is_the_default_without_config(self) -> None:
        self.write_brand("officekit")
        self.assertEqual(catalog.default_brand_id(self.root), "officekit")

    def test_config_default_wins_when_several_brands_exist(self) -> None:
        self.write_brand("officekit")
        self.write_brand("acme")
        (self.root / "config.toml").write_text(
            '[brand]\ndefault = "acme"\n', encoding="utf-8"
        )
        self.assertEqual(catalog.default_brand_id(self.root), "acme")
        self.assertEqual(catalog.resolve_brand_id(self.root, None), "acme")
        self.assertEqual(catalog.resolve_brand_id(self.root, "officekit"), "officekit")

    def test_several_brands_without_a_default_are_an_error(self) -> None:
        self.write_brand("officekit")
        self.write_brand("acme")
        with self.assertRaises(catalog.BrandCatalogError):
            catalog.default_brand_id(self.root)

    def test_missing_configured_default_is_an_error(self) -> None:
        self.write_brand("officekit")
        (self.root / "config.toml").write_text(
            '[brand]\ndefault = "missing"\n', encoding="utf-8"
        )
        with self.assertRaises(catalog.BrandCatalogError):
            catalog.default_brand_id(self.root)

    def test_workspace_root_is_config_or_a_brand_catalog(self) -> None:
        self.assertFalse(catalog.is_workspace_root(self.root))
        (self.root / "config.toml").write_text("[document]\n", encoding="utf-8")
        self.assertTrue(catalog.is_workspace_root(self.root))
        (self.root / "config.toml").unlink()
        self.write_brand("officekit")
        self.assertTrue(catalog.is_workspace_root(self.root))


if __name__ == "__main__":
    unittest.main()
