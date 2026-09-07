from __future__ import annotations

import base64
import contextlib
import importlib.util
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "document" / "package.py"
SPEC = importlib.util.spec_from_file_location("document_package", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
document_package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = document_package
SPEC.loader.exec_module(document_package)

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/6HYlwAAAAAASUVORK5CYII="
)
LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8">'
    '<rect width="8" height="8" fill="#7C3AED"/></svg>\n'
)
TOKENS_CSS = """\
@import url("https://fonts.example/css2?family=Inter");

:root {
  --color-primary: #7C3AED;
  --brand-logo: url("assets/logo.svg");
}
"""
STYLES_CSS = """\
body { color: var(--color-primary); }
.brand-mark { background-image: url("../../brand/assets/logo.svg"); }
.glyph { fill: url(#gradient); }
"""
SCRIPT_JS = 'console.log("demo-script-marker");\n'

DATA_URI_RE = re.compile(r'src="(data:[^"]+)"')


def data_uri_payload(uri: str) -> tuple[str, bytes]:
    header, _, encoded = uri.partition(",")
    mime = header[len("data:") :].removesuffix(";base64")
    return mime, base64.b64decode(encoded)


def snapshot(root: Path, *, skip: Path | None = None) -> dict[str, bytes]:
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if skip is not None and skip in path.parents:
            continue
        files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


class DocumentPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)
        self.root = self.tmp / "ws"
        self.project = self.root / "projects" / "demo"

        (self.root / "brand" / "assets").mkdir(parents=True)
        (self.project / "assets").mkdir(parents=True)
        (self.root / "brand" / "brand.json").write_text("{}", encoding="utf-8")
        (self.root / "brand" / "tokens.css").write_text(TOKENS_CSS, encoding="utf-8")
        (self.root / "brand" / "assets" / "logo.svg").write_text(
            LOGO_SVG, encoding="utf-8"
        )
        (self.project / "styles.css").write_text(STYLES_CSS, encoding="utf-8")
        (self.project / "script.js").write_text(SCRIPT_JS, encoding="utf-8")
        (self.project / "assets" / "pic.png").write_bytes(PNG_BYTES)

    def write_index(self, body: str) -> Path:
        entry = self.project / "index.html"
        entry.write_text(body, encoding="utf-8")
        return entry

    def package(self, body: str) -> str:
        return document_package.package_document(self.write_index(body)).html

    # -- inlining ---------------------------------------------------------

    def test_inlines_stylesheets_scripts_and_images(self) -> None:
        packaged = self.package(
            """<!doctype html>
<html lang="en">
  <head>
    <link rel="stylesheet" href="../../brand/tokens.css" />
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <img src="assets/pic.png" alt="Chart" width="1" height="1" />
    <script src="script.js" defer></script>
  </body>
</html>
"""
        )

        self.assertNotIn("<link", packaged)
        self.assertNotIn('href="styles.css"', packaged)
        self.assertEqual(packaged.count("<style>"), 2)
        self.assertIn("--color-primary: #7C3AED;", packaged)
        self.assertIn("body { color: var(--color-primary); }", packaged)

        self.assertNotIn('src="script.js"', packaged)
        self.assertIn('console.log("demo-script-marker");', packaged)

        self.assertNotIn('src="assets/pic.png"', packaged)
        uris = DATA_URI_RE.findall(packaged)
        self.assertEqual(len(uris), 1)
        mime, payload = data_uri_payload(uris[0])
        self.assertEqual(mime, "image/png")
        self.assertEqual(payload, PNG_BYTES)
        # Sibling attributes on the rewritten tag survive untouched.
        self.assertIn('alt="Chart" width="1" height="1"', packaged)

    def test_css_urls_resolve_against_the_referring_stylesheet(self) -> None:
        packaged = self.package(
            '<link rel="stylesheet" href="../../brand/tokens.css">\n'
            '<link rel="stylesheet" href="styles.css">\n'
        )

        # tokens.css names the logo as `assets/logo.svg` (relative to brand/) and
        # styles.css as `../../brand/assets/logo.svg`; both must land on the file.
        expected = document_package.data_uri(LOGO_SVG.encode("utf-8"), "image/svg+xml")
        self.assertEqual(packaged.count(f'url("{expected}")'), 2)
        self.assertNotIn('url("assets/logo.svg")', packaged)
        self.assertNotIn("../../brand/assets/logo.svg", packaged)

    def test_inlines_urls_inside_an_inline_style_block(self) -> None:
        packaged = self.package(
            '<style media="screen">\n'
            '  .mark { background-image: url("../../brand/assets/logo.svg"); }\n'
            "</style>\n"
        )

        self.assertIn('<style media="screen">', packaged)
        self.assertIn('url("data:image/svg+xml;base64,', packaged)
        self.assertNotIn("../../brand/assets/logo.svg", packaged)

    def test_inlines_local_css_imports_and_rejects_cycles(self) -> None:
        (self.project / "partial.css").write_text(
            ".partial { color: rebeccapurple; }\n", encoding="utf-8"
        )
        (self.project / "styles.css").write_text(
            '@import url("partial.css");\nbody { margin: 0; }\n', encoding="utf-8"
        )

        packaged = self.package('<link rel="stylesheet" href="styles.css">')
        self.assertIn(".partial { color: rebeccapurple; }", packaged)
        self.assertNotIn('@import url("partial.css")', packaged)

        (self.project / "partial.css").write_text(
            '@import url("styles.css");\n', encoding="utf-8"
        )
        with self.assertRaisesRegex(document_package.PackageError, "cycle"):
            self.package('<link rel="stylesheet" href="styles.css">')

    # -- pass-through -----------------------------------------------------

    def test_remote_and_fragment_references_are_untouched(self) -> None:
        source = """<!doctype html>
<html lang="en">
  <head>
    <link rel="stylesheet" href="https://cdn.example/reset.css">
    <link rel="preload" href="fonts/inter.woff2" as="font">
    <style>
      .glyph { fill: url(#gradient); }
      @import url("//cdn.example/late.css");
    </style>
  </head>
  <body>
    <a href="#section">Skip</a>
    <img src="https://cdn.example/photo.png" alt="Remote">
    <img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt="Inline">
    <script src="https://cdn.example/app.js"></script>
  </body>
</html>
"""
        entry = self.write_index(source)
        result = document_package.package_document(entry)

        self.assertEqual(result.html, source)
        self.assertEqual(result.sources, (entry.resolve(),))
        # A local `rel="preload"` href is out of scope and stays as authored.
        self.assertIn('href="fonts/inter.woff2"', result.html)

    def test_remote_font_import_survives_stylesheet_inlining(self) -> None:
        packaged = self.package('<link rel="stylesheet" href="../../brand/tokens.css">')
        self.assertIn(
            '@import url("https://fonts.example/css2?family=Inter");', packaged
        )

    # -- failures ---------------------------------------------------------

    def test_missing_references_fail(self) -> None:
        for body in (
            '<link rel="stylesheet" href="missing.css">',
            '<img src="assets/missing.png" alt="Gone">',
            '<script src="missing.js"></script>',
        ):
            with self.subTest(body=body), self.assertRaisesRegex(
                document_package.PackageError, "missing file"
            ):
                self.package(body)

    def test_missing_reference_inside_a_stylesheet_fails(self) -> None:
        (self.project / "styles.css").write_text(
            '.mark { background-image: url("assets/gone.svg"); }\n', encoding="utf-8"
        )
        with self.assertRaisesRegex(document_package.PackageError, "missing file"):
            self.package('<link rel="stylesheet" href="styles.css">')

    def test_references_outside_the_workspace_are_rejected(self) -> None:
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "secret.css").write_text("body { color: red; }\n", encoding="utf-8")
        (outside / "pixel.png").write_bytes(PNG_BYTES)

        for body in (
            '<link rel="stylesheet" href="../../../outside/secret.css">',
            '<img src="../../../outside/pixel.png" alt="Escaped">',
            '<script src="../../../outside/secret.css"></script>',
        ):
            with self.subTest(body=body), self.assertRaisesRegex(
                document_package.PackageError, "outside the workspace root"
            ):
                self.package(body)

    def test_stylesheet_cannot_escape_the_workspace_either(self) -> None:
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "pixel.png").write_bytes(PNG_BYTES)
        (self.project / "styles.css").write_text(
            '.mark { background-image: url("../../../outside/pixel.png"); }\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            document_package.PackageError, "outside the workspace root"
        ):
            self.package('<link rel="stylesheet" href="styles.css">')

    def test_root_relative_paths_are_rejected(self) -> None:
        with self.assertRaisesRegex(
            document_package.PackageError, "root-relative path"
        ):
            self.package('<img src="/assets/pic.png" alt="Absolute">')

    def test_workspace_root_is_required(self) -> None:
        stray = self.tmp / "stray"
        stray.mkdir()
        entry = stray / "index.html"
        entry.write_text("<p>No workspace here.</p>", encoding="utf-8")
        with self.assertRaisesRegex(
            document_package.PackageError, "cannot find the workspace root"
        ):
            document_package.package_document(entry)

    def test_missing_entry_file_fails(self) -> None:
        with self.assertRaisesRegex(document_package.PackageError, "does not exist"):
            document_package.package_document(self.project / "nope.html")

    # -- output handling --------------------------------------------------

    def test_output_colliding_with_a_source_is_rejected(self) -> None:
        entry = self.write_index(
            '<link rel="stylesheet" href="styles.css">\n'
            '<script src="script.js" defer></script>\n'
        )
        result = document_package.package_document(entry)

        for collision in (
            entry,
            self.project / "styles.css",
            self.project / "script.js",
        ):
            with self.subTest(collision=collision.name), self.assertRaisesRegex(
                document_package.PackageError, "source files"
            ):
                document_package.write_package(result, collision)

    def test_writes_artifact_and_creates_the_output_parent(self) -> None:
        entry = self.write_index(
            '<link rel="stylesheet" href="styles.css">\n'
            '<img src="assets/pic.png" alt="Chart">\n'
        )
        result = document_package.package_document(entry)
        output = self.project / "dist" / "nested" / "demo.html"

        written = document_package.write_package(result, output)

        self.assertEqual(written, output.resolve())
        self.assertEqual(output.read_text(encoding="utf-8"), result.html)
        self.assertFalse(list(output.parent.glob(".*.tmp")))

    def test_source_files_are_never_modified(self) -> None:
        entry = self.write_index(
            '<link rel="stylesheet" href="../../brand/tokens.css">\n'
            '<link rel="stylesheet" href="styles.css">\n'
            '<img src="assets/pic.png" alt="Chart">\n'
            '<script src="script.js" defer></script>\n'
        )
        dist = self.project / "dist"
        before = snapshot(self.root)

        result = document_package.package_document(entry)
        document_package.write_package(result, dist / "demo.html")

        self.assertEqual(snapshot(self.root, skip=dist), before)

    # -- CLI --------------------------------------------------------------

    def test_cli_packages_a_document(self) -> None:
        entry = self.write_index(
            '<link rel="stylesheet" href="styles.css">\n'
            '<script src="script.js" defer></script>\n'
        )
        output = self.project / "dist" / "demo.html"

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = document_package.main([str(entry), str(output)])

        self.assertEqual(code, 0)
        # styles.css, the logo it points at, and script.js.
        self.assertIn("Inlined 3 local file(s)", stdout.getvalue())
        self.assertIn('console.log("demo-script-marker");', output.read_text())

    def test_cli_reports_errors_without_writing(self) -> None:
        entry = self.write_index('<link rel="stylesheet" href="missing.css">')
        output = self.project / "dist" / "demo.html"

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = document_package.main([str(entry), str(output)])

        self.assertEqual(code, 2)
        self.assertIn("error: ", stderr.getvalue())
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
