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
MODULE_PATH = ROOT / "scripts" / "document" / "doc.py"
SPEC = importlib.util.spec_from_file_location("document_doc", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
document_doc = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = document_doc
SPEC.loader.exec_module(document_doc)

SECTIONS = """\
      <section id="findings" aria-labelledby="findings-heading">
        <h2 id="findings-heading">Findings</h2>
        <p class="lede">What we learned.</p>
      </section>

      <section id="next-steps" aria-labelledby="next-steps-heading">
        <h2 id="next-steps-heading">Next steps</h2>
        <p>What happens now.</p>
      </section>\
"""

LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8">'
    '<rect width="8" height="8" fill="#7C3AED"/></svg>\n'
)


def run(*argv: str) -> tuple[int, str]:
    """Invoke the CLI, returning its exit code and captured stdout."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = document_doc.main(list(argv))
    return code, buffer.getvalue()


class DocumentPipelineTestCase(unittest.TestCase):
    """A throwaway workspace carrying the real template and brand files."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        brand = self.root / "brands" / "officekit"
        (brand / "assets").mkdir(parents=True)
        (self.root / ".templates" / "document-html").mkdir(parents=True)
        (self.root / "config.toml").write_text(
            '[brand]\ndefault = "officekit"\n', encoding="utf-8"
        )
        for name in ("brand.json", "tokens.css"):
            shutil.copy(ROOT / "brands" / "officekit" / name, brand / name)
        for name in ("logo.svg", "logo-light.svg"):
            (brand / "assets" / name).write_text(LOGO_SVG, encoding="utf-8")
        shutil.copy(
            ROOT / ".templates" / "document-html" / "document.html",
            self.root / ".templates" / "document-html" / "document.html",
        )

    # -- helpers ----------------------------------------------------------

    def scaffold(self, slug: str = "review", **extra: str) -> Path:
        argv = ["new", slug, "--workspace-root", str(self.root)]
        for key, value in extra.items():
            argv += [f"--{key}", value]
        code, _ = run(*argv)
        self.assertEqual(code, 0)
        return self.root / "projects" / slug / f"{slug}.html"

    def author(self, path: Path, sections: str = SECTIONS) -> None:
        text = path.read_text(encoding="utf-8")
        self.assertIn(document_doc.CONTENT_MARKER, text)
        path.write_text(
            text.replace(document_doc.CONTENT_MARKER, sections), encoding="utf-8"
        )

    def complete(self, slug: str = "review", sections: str = SECTIONS) -> Path:
        path = self.scaffold(slug, title="Quarterly Review")
        self.author(path, sections)
        self.assertEqual(run("toc", str(path))[0], 0)
        return path

    def check(self, path: Path) -> tuple[int, str]:
        return run("check", str(path))


class NewTests(DocumentPipelineTestCase):
    def test_scaffold_produces_one_branded_self_contained_file(self) -> None:
        path = self.scaffold(title="Quarterly Review", subtitle="Q3 FY26")
        self.assertTrue(path.is_file())
        # One file, not a directory of parts.
        self.assertEqual([p.name for p in path.parent.iterdir()], [path.name])

        text = path.read_text(encoding="utf-8")
        self.assertIn("<title>Quarterly Review</title>", text)
        self.assertIn("Q3 FY26", text)
        # Brand values are inlined from the token sheet, not linked.
        self.assertIn("--color-primary: #7C3AED;", text)
        self.assertIn("officekit:brand-id: officekit", text)
        self.assertIn('--brand-logo: url("data:image/svg+xml;base64,', text)
        self.assertNotIn('<link rel="stylesheet"', text)
        self.assertNotIn("tokens.css\"", text)

    def test_scaffold_strips_template_hints_and_placeholders(self) -> None:
        text = self.scaffold().read_text(encoding="utf-8")
        self.assertNotIn("officekit:hint", text)
        self.assertNotIn("{{", text)

    def test_absent_subtitle_and_footer_are_removed_not_emptied(self) -> None:
        text = self.scaffold().read_text(encoding="utf-8")
        self.assertNotIn('<p class="subtitle">', text)
        self.assertNotIn('<footer class="doc-footer">', text)

    def test_footer_is_kept_when_supplied(self) -> None:
        text = self.scaffold(footer="Internal only").read_text(encoding="utf-8")
        self.assertIn("Internal only", text)
        self.assertIn('<footer class="doc-footer">', text)

    def test_title_defaults_to_the_slug(self) -> None:
        text = self.scaffold("ops-handover").read_text(encoding="utf-8")
        self.assertIn("<title>Ops Handover</title>", text)

    def test_rejects_an_unusable_slug(self) -> None:
        code, output = run("new", "Not A Slug", "--workspace-root", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("not a usable slug", output)

    def test_refuses_to_clobber_an_existing_document(self) -> None:
        self.scaffold()
        code, output = run("new", "review", "--workspace-root", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("already exists", output)

        code, _ = run("new", "review", "--force", "--workspace-root", str(self.root))
        self.assertEqual(code, 0)

    def test_reports_a_missing_token_sheet_instead_of_guessing(self) -> None:
        (self.root / "brands" / "officekit" / "tokens.css").unlink()
        code, output = run("new", "review", "--workspace-root", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("brands/officekit/tokens.css is missing", output)

    def test_scaffold_can_bind_a_named_brand(self) -> None:
        other = self.root / "brands" / "acme"
        shutil.copytree(self.root / "brands" / "officekit", other)
        tokens = other / "tokens.css"
        tokens.write_text(
            tokens.read_text(encoding="utf-8").replace("#7C3AED", "#0F766E"),
            encoding="utf-8",
        )
        path = self.scaffold("acme-memo", title="Acme Memo", brand="acme")
        text = path.read_text(encoding="utf-8")
        self.assertIn("officekit:brand-id: acme", text)
        self.assertIn("--color-primary: #0F766E;", text)
        branded = text.split("officekit:brand:end", 1)[0]
        self.assertNotIn("#7C3AED", branded)

    def test_rejects_an_unknown_brand(self) -> None:
        code, output = run(
            "new", "review", "--brand", "missing", "--workspace-root", str(self.root)
        )
        self.assertEqual(code, 2)
        self.assertIn("does not exist", output)

    def test_reports_a_mark_named_but_missing(self) -> None:
        (self.root / "brands" / "officekit" / "assets" / "logo.svg").unlink()
        code, output = run("new", "review", "--workspace-root", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("missing", output)


class TocTests(DocumentPipelineTestCase):
    def test_contents_list_is_generated_from_the_sections(self) -> None:
        path = self.scaffold(title="Quarterly Review")
        self.author(path)
        code, output = run("toc", str(path))
        self.assertEqual(code, 0)
        self.assertIn("2 section(s)", output)

        text = path.read_text(encoding="utf-8")
        self.assertIn('<li><a href="#findings">Findings</a></li>', text)
        self.assertIn('<li><a href="#next-steps">Next steps</a></li>', text)

    def test_rebuild_is_idempotent(self) -> None:
        path = self.complete()
        before = path.read_text(encoding="utf-8")
        code, output = run("toc", str(path))
        self.assertEqual(code, 0)
        self.assertIn("already lists", output)
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_nested_sections_stay_out_of_the_contents(self) -> None:
        nested = """\
      <section id="outer" aria-labelledby="outer-heading">
        <h2 id="outer-heading">Outer</h2>
        <section id="inner" aria-labelledby="inner-heading">
          <h3 id="inner-heading">Inner</h3>
          <p>Body.</p>
        </section>
      </section>\
"""
        path = self.complete(sections=nested)
        text = path.read_text(encoding="utf-8")
        self.assertIn('href="#outer"', text)
        self.assertNotIn('href="#inner"', text)

    def test_headings_with_markup_are_escaped_into_the_list(self) -> None:
        sections = """\
      <section id="config" aria-labelledby="config-heading">
        <h2 id="config-heading">The <code>a &amp; b</code> file</h2>
        <p>Body.</p>
      </section>\
"""
        path = self.complete(sections=sections)
        self.assertIn("The a &amp; b file", path.read_text(encoding="utf-8"))


class CheckTests(DocumentPipelineTestCase):
    def test_a_finished_document_passes(self) -> None:
        path = self.complete()
        code, output = self.check(path)
        self.assertEqual(code, 0, output)
        self.assertIn("PASS", output)
        self.assertIn("self-contained", output)
        self.assertIn("file://", output)

    def test_unwritten_content_fails(self) -> None:
        path = self.scaffold(title="Quarterly Review")
        code, output = self.check(path)
        self.assertEqual(code, 1)
        self.assertIn("officekit:content marker is still", output)

    def test_a_local_reference_fails_and_embed_fixes_it(self) -> None:
        path = self.complete()
        (path.parent / "chart.svg").write_text(LOGO_SVG, encoding="utf-8")
        text = path.read_text(encoding="utf-8").replace(
            "<p>What happens now.</p>",
            '<p>What happens now.</p>\n        <img src="chart.svg" alt="A chart" />',
        )
        path.write_text(text, encoding="utf-8")

        code, output = self.check(path)
        self.assertEqual(code, 1)
        self.assertIn("points at a local file", output)

        code, output = run("embed", str(path))
        self.assertEqual(code, 0, output)
        self.assertIn("Inlined 1 local file", output)
        self.assertEqual(self.check(path)[0], 0)

    def test_a_hand_edited_brand_region_fails(self) -> None:
        path = self.complete()
        text = path.read_text(encoding="utf-8").replace(
            "--color-primary: #7C3AED;", "--color-primary: #FF0000;"
        )
        path.write_text(text, encoding="utf-8")

        code, output = self.check(path)
        self.assertEqual(code, 1)
        self.assertIn("no longer matches officekit", output)

    def test_an_image_without_alt_text_fails(self) -> None:
        path = self.complete()
        text = path.read_text(encoding="utf-8").replace(
            "<p>What happens now.</p>",
            '<p>What happens now.</p>\n        <img src="data:image/svg+xml;base64,AA==" />',
        )
        path.write_text(text, encoding="utf-8")
        code, output = self.check(path)
        self.assertEqual(code, 1)
        self.assertIn("no alt attribute", output)

    def test_a_decorative_image_may_omit_alt(self) -> None:
        path = self.complete()
        text = path.read_text(encoding="utf-8").replace(
            "<p>What happens now.</p>",
            '<p>What happens now.</p>\n        '
            '<img src="data:image/svg+xml;base64,AA==" aria-hidden="true" />',
        )
        path.write_text(text, encoding="utf-8")
        self.assertEqual(self.check(path)[0], 0)

    def test_a_skipped_heading_level_fails(self) -> None:
        sections = """\
      <section id="findings" aria-labelledby="findings-heading">
        <h2 id="findings-heading">Findings</h2>
        <h4>Too deep</h4>
        <p>Body.</p>
      </section>\
"""
        path = self.complete(sections=sections)
        code, output = self.check(path)
        self.assertEqual(code, 1)
        self.assertIn("heading level jumps from h2 to h4", output)

    def test_a_dangling_in_page_link_fails(self) -> None:
        path = self.complete()
        text = path.read_text(encoding="utf-8").replace(
            "<p>What happens now.</p>",
            '<p>See <a href="#appendix">the appendix</a>.</p>',
        )
        path.write_text(text, encoding="utf-8")
        code, output = self.check(path)
        self.assertEqual(code, 1)
        self.assertIn("#appendix has no matching id", output)

    def test_a_stale_contents_list_fails(self) -> None:
        path = self.complete()
        text = path.read_text(encoding="utf-8").replace(
            '<li><a href="#next-steps">Next steps</a></li>\n', ""
        )
        path.write_text(text, encoding="utf-8")
        code, output = self.check(path)
        self.assertEqual(code, 1)
        self.assertIn("does not match the sections", output)

    def test_leftover_placeholder_copy_fails(self) -> None:
        path = self.complete()
        text = path.read_text(encoding="utf-8").replace(
            "<p>What happens now.</p>", "<p>TODO: write this bit.</p>"
        )
        path.write_text(text, encoding="utf-8")
        code, output = self.check(path)
        self.assertEqual(code, 1)
        self.assertIn("TODO", output)

    def test_a_section_without_a_heading_fails(self) -> None:
        sections = """\
      <section id="orphan">
        <p>No heading here.</p>
      </section>\
"""
        path = self.complete(sections=sections)
        code, output = self.check(path)
        self.assertEqual(code, 1)
        self.assertIn("has no <h2>", output)

    def test_a_remote_reference_warns_but_passes(self) -> None:
        path = self.complete()
        text = path.read_text(encoding="utf-8").replace(
            "<p>What happens now.</p>",
            '<p>What happens now.</p>\n        '
            '<img src="https://example.com/chart.png" alt="A chart" />',
        )
        path.write_text(text, encoding="utf-8")
        code, output = self.check(path)
        self.assertEqual(code, 0, output)
        self.assertIn("needs the network", output)

    def test_the_webfont_import_is_not_treated_as_a_local_reference(self) -> None:
        path = self.complete()
        self.assertIn("fonts.googleapis.com", path.read_text(encoding="utf-8"))
        self.assertEqual(self.check(path)[0], 0)


class RefreshTests(DocumentPipelineTestCase):
    def test_refresh_restores_a_drifted_brand_region(self) -> None:
        path = self.complete()
        text = path.read_text(encoding="utf-8").replace(
            "--color-primary: #7C3AED;", "--color-primary: #FF0000;"
        )
        path.write_text(text, encoding="utf-8")
        self.assertEqual(self.check(path)[0], 1)

        code, output = run("refresh", str(path))
        self.assertEqual(code, 0, output)
        self.assertIn("Refreshed the brand", output)
        self.assertEqual(self.check(path)[0], 0)

    def test_refresh_propagates_a_brand_change(self) -> None:
        path = self.complete()
        tokens = self.root / "brands" / "officekit" / "tokens.css"
        tokens.write_text(
            tokens.read_text(encoding="utf-8").replace("#7C3AED", "#0F766E"),
            encoding="utf-8",
        )
        # The document still carries the old palette until it is refreshed.
        self.assertEqual(self.check(path)[0], 1)

        self.assertEqual(run("refresh", "--all", "--workspace-root", str(self.root))[0], 0)
        self.assertIn("#0F766E", path.read_text(encoding="utf-8"))
        self.assertEqual(self.check(path)[0], 0)

    def test_refresh_keeps_each_document_on_its_own_brand(self) -> None:
        other = self.root / "brands" / "acme"
        shutil.copytree(self.root / "brands" / "officekit", other)
        other.joinpath("tokens.css").write_text(
            other.joinpath("tokens.css")
            .read_text(encoding="utf-8")
            .replace("#7C3AED", "#0F766E"),
            encoding="utf-8",
        )
        office = self.complete("review")
        acme = self.scaffold("acme-memo", title="Acme", brand="acme")
        self.author(acme)
        self.assertEqual(run("toc", str(acme))[0], 0)

        for path, old in ((office, "#7C3AED"), (acme, "#0F766E")):
            path.write_text(
                path.read_text(encoding="utf-8").replace(old, "#FF0000"),
                encoding="utf-8",
            )

        self.assertEqual(
            run("refresh", "--all", "--workspace-root", str(self.root))[0], 0
        )
        office_text = office.read_text(encoding="utf-8")
        acme_text = acme.read_text(encoding="utf-8")
        self.assertIn("#7C3AED", office_text)
        self.assertIn("officekit:brand-id: officekit", office_text)
        self.assertIn("#0F766E", acme_text)
        self.assertIn("officekit:brand-id: acme", acme_text)

    def test_refresh_is_a_no_op_when_already_current(self) -> None:
        path = self.complete()
        code, output = run("refresh", str(path))
        self.assertEqual(code, 0)
        self.assertIn("already current", output)

    def test_refresh_needs_a_target(self) -> None:
        code, output = run("refresh", "--workspace-root", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("name at least one document", output)


class ShellTests(DocumentPipelineTestCase):
    """A one-file document is self-contained, not frozen.

    Every rule a document needs was copied into it at scaffold time, so a fix
    made to the template afterwards would otherwise never reach it. These cover
    the two spans the template owns, and the boundary that keeps a refresh from
    touching anything else.
    """

    def edit_template(self, old: str, new: str) -> None:
        path = self.root / ".templates" / "document-html" / "document.html"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def test_a_style_fix_reaches_a_document_that_already_exists(self) -> None:
        path = self.complete()
        self.edit_template("--doc-rail: 14rem;", "--doc-rail: 18rem;")

        # Out of date is advisory: the document still renders, so check passes
        # while saying what it is missing.
        code, output = self.check(path)
        self.assertEqual(code, 0, output)
        self.assertIn("shared styles block is older", output)

        code, output = run("refresh", str(path))
        self.assertEqual(code, 0, output)
        self.assertIn("shared styles", output)
        self.assertIn("--doc-rail: 18rem;", path.read_text(encoding="utf-8"))
        self.assertNotIn("is older", self.check(path)[1])

    def test_a_script_fix_reaches_a_document_that_already_exists(self) -> None:
        path = self.complete()
        self.edit_template('"use strict";', '"use strict";\n        const fixed = 1;')

        code, output = self.check(path)
        self.assertEqual(code, 0, output)
        self.assertIn("shared script block is older", output)

        code, output = run("refresh", str(path))
        self.assertEqual(code, 0, output)
        self.assertIn("shared script", output)
        self.assertIn("const fixed = 1;", path.read_text(encoding="utf-8"))

    def test_a_refresh_leaves_the_document_s_own_work_alone(self) -> None:
        path = self.complete()
        own_css = ".doc-body table { font-variant-numeric: tabular-nums; }"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                document_doc.STYLES_START,
                f"{document_doc.STYLES_START}\n      {own_css}",
            ),
            encoding="utf-8",
        )
        self.edit_template("--doc-rail: 14rem;", "--doc-rail: 18rem;")

        self.assertEqual(run("refresh", str(path))[0], 0)
        text = path.read_text(encoding="utf-8")
        self.assertIn(own_css, text)
        self.assertIn("--doc-rail: 18rem;", text)
        self.assertIn("Findings", text)
        self.assertEqual(self.check(path)[0], 0)

    def test_a_document_without_the_markers_is_reported_not_rewritten(self) -> None:
        """A hand-migrated file: its own code and the template's are the same
        text, so guessing the boundary would risk eating the author's work."""
        path = self.complete()
        path.write_text(
            path.read_text(encoding="utf-8").replace(document_doc.SCRIPT_START, ""),
            encoding="utf-8",
        )
        self.edit_template('"use strict";', '"use strict";\n        const fixed = 1;')

        code, output = run("refresh", str(path))
        self.assertEqual(code, 0, output)
        self.assertIn("no shared script markers", output)
        self.assertNotIn("const fixed = 1;", path.read_text(encoding="utf-8"))

    def test_a_missing_template_does_not_stop_a_brand_refresh(self) -> None:
        path = self.complete()
        (self.root / ".templates" / "document-html" / "document.html").unlink()
        tokens = self.root / "brands" / "officekit" / "tokens.css"
        tokens.write_text(
            tokens.read_text(encoding="utf-8").replace("#7C3AED", "#0F766E"),
            encoding="utf-8",
        )

        code, output = run("refresh", str(path))
        self.assertEqual(code, 0, output)
        self.assertIn("refreshing the brand only", output)
        self.assertIn("#0F766E", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
