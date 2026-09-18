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


class PresentationTemplateContractTests(unittest.TestCase):
    """Layout bugs found in review belong in the template, not one deck."""

    def test_two_column_layouts_keep_a_gutter(self) -> None:
        css = (ROOT / ".templates" / "presentation" / "styles" / "brand.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("div.slidev-layout.two-cols-header", css)
        self.assertIn("div.slidev-layout.two-columns", css)
        self.assertIn("column-gap: 4rem", css)
        self.assertIn("minmax(0, 1fr)", css)
        self.assertIn("align-items: start", css)
        self.assertIn("padding: 1rem 1.25rem 1.15rem", css)
        self.assertIn("border-radius: 0.75rem", css)
        self.assertIn(".ok-icon", css)
        self.assertIn("color: var(--ok-primary)", css)

    def test_template_ships_reusable_ok_classes(self) -> None:
        css = (ROOT / ".templates" / "presentation" / "styles" / "brand.css").read_text(
            encoding="utf-8"
        )
        for name in (
            ".ok-hero",
            ".ok-hero-num",
            ".ok-bands",
            ".ok-band",
            ".ok-flow",
            ".ok-step",
            ".ok-outcome",
            ".ok-cover",
            ".ok-icon-line",
        ):
            self.assertIn(name, css)

    def test_template_carries_the_review_fixes(self) -> None:
        """Each of these was a filed issue against a real deck."""
        template = ROOT / ".templates" / "presentation"
        css = (template / "styles" / "brand.css").read_text(encoding="utf-8")
        # #24 the brand accent is reachable from ok-* classes.
        self.assertIn("--ok-accent: var(--color-accent, var(--ok-secondary))", css)
        # #19 icons follow the ground of inverted containers.
        self.assertRegex(css, r"\.ok-band \.ok-icon[^{]*\{[^}]*currentColor")
        # #25 / #22 inline code is pinned to tokens in every scheme.
        self.assertIn(".slidev-layout :not(pre) > code", css)
        # #22 hero number has a display scale without a <span>.
        self.assertRegex(css, r"\.ok-hero-num \{[^}]*font-size: 3\.1rem")
        # #22 the rule centres under centred type.
        self.assertIn(".slidev-layout.statement .ok-rule", css)
        # #18 the end layout is replaced, not out-specificity-ed.
        end = template / "layouts" / "end.vue"
        self.assertTrue(end.is_file())
        self.assertIn('class="slidev-layout end ok-end"', end.read_text(encoding="utf-8"))
        self.assertIn(".slidev-layout.end.ok-end", css)
        # #25 the scaffold pins the colour scheme.
        slides = (template / "slides.md.j2").read_text(encoding="utf-8")
        self.assertIn("colorSchema: light", slides)
        # #22 the watermark is positioned inside the slide box.
        footer = (template / "global-bottom.vue").read_text(encoding="utf-8")
        self.assertIn("position: absolute", footer)
        self.assertNotIn("position: fixed", footer)
        # #27 floating-vue is pinned for the twoslash client patch.
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["overrides"]["floating-vue"], "5.2.2")

    def test_log_errors_dedupes_and_strips_ansi(self) -> None:
        text = (
            "  \x1b[32m➜\x1b[39m  Local: http://localhost:3030/\n"
            "[vite] (client) [console.error] Failed to patch FloatingVue TypeError: x\n"
            "    at app.component (…/client.mjs:27:42)\n"
            "[vite] (client) [console.error] Failed to patch FloatingVue TypeError: x\n"
            "[vite] Internal server error: Failed to resolve import\n"
        )
        self.assertEqual(
            deck.log_errors(text),
            [
                "[vite] (client) [console.error] Failed to patch FloatingVue TypeError: x",
                "[vite] Internal server error: Failed to resolve import",
            ],
        )

    def test_template_vocabulary_covers_core_layouts(self) -> None:
        slides = (ROOT / ".templates" / "presentation" / "slides.md.j2").read_text(
            encoding="utf-8"
        )
        for layout in (
            "cover",
            "section",
            "statement",
            "two-cols",
            "two-cols-header",
            "fact",
            "quote",
            "image-right",
            "end",
        ):
            self.assertIn(f"layout: {layout}", slides)


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
            "--no-install",
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
        self.assertIn("@iconify-json/lucide", package)
        self.assertIn("<lucide-presentation", slides)
        self.assertIn("layout: cover", slides)
        self.assertIn("layout: end", slides)
        self.assertIn("http://localhost:3030/", output)
        self.assertIn("deck.py dev kickoff", output)
        self.assertIn("skip:", output)
        self.assertFalse((dest / "style.css.j2").exists())

    def test_new_can_bind_a_named_brand(self) -> None:
        other = self.root / "brands" / "acme"
        shutil.copytree(self.root / "brands" / "officekit", other)
        code, output = run(
            "new",
            "acme-pitch",
            "--brand",
            "acme",
            "--no-install",
            "--workspace-root",
            str(self.root),
        )
        self.assertEqual(code, 0, output)
        style = (self.root / "projects" / "acme-pitch" / "style.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("../../brands/acme/tokens.css", style)

    def test_refuses_to_clobber_an_existing_project(self) -> None:
        run("new", "kickoff", "--no-install", "--workspace-root", str(self.root))
        code, output = run(
            "new", "kickoff", "--no-install", "--workspace-root", str(self.root)
        )
        self.assertEqual(code, 2)
        self.assertIn("already exists", output)
        code, output = run(
            "new",
            "kickoff",
            "--force",
            "--no-install",
            "--title",
            "Retitled",
            "--workspace-root",
            str(self.root),
        )
        self.assertEqual(code, 0, output)
        self.assertIn(
            "title: Retitled",
            (self.root / "projects" / "kickoff" / "slides.md").read_text(encoding="utf-8"),
        )


class DeckAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        shutil.copytree(ROOT / "brands" / "officekit", self.root / "brands" / "officekit")
        # Point layout/icon discovery at the real workspace node_modules.
        nm = self.root / "node_modules"
        nm.mkdir()
        for rel in (
            Path("@slidev") / "client" / "layouts",
            Path("@slidev") / "theme-default" / "layouts",
            Path("@iconify-json") / "lucide",
        ):
            source = ROOT / "node_modules" / rel
            if source.exists():
                dest = nm / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(source, dest)

    def _write_deck(self, slides: str, style: str | None = None) -> Path:
        dest = self.root / "projects" / "bad-deck"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "slides.md").write_text(slides, encoding="utf-8")
        styles = dest / "styles"
        styles.mkdir(exist_ok=True)
        (styles / "brand.css").write_text("/* ok */\n", encoding="utf-8")
        if style is None:
            style = (
                '@import "../../brands/officekit/tokens.css";\n'
                '@import "./styles/brand.css";\n'
                ':root { --ok-logo: url("../../brands/officekit/assets/logo.svg"); }\n'
            )
        (dest / "style.css").write_text(style, encoding="utf-8")
        return dest

    def test_scaffold_passes_audit(self) -> None:
        shutil.copytree(
            ROOT / ".templates" / "presentation",
            self.root / ".templates" / "presentation",
        )
        shutil.copy(ROOT / "config.toml", self.root / "config.toml")
        code, output = run(
            "new",
            "good-deck",
            "--no-install",
            "--workspace-root",
            str(self.root),
        )
        self.assertEqual(code, 0, output)
        # Link workspace node_modules into the temp root already done in setUp.
        code, output = run("audit", "good-deck", "--workspace-root", str(self.root))
        self.assertEqual(code, 0, output)
        self.assertIn("PASS", output)

    def test_unknown_layout_fails(self) -> None:
        self._write_deck(
            """---
theme: default
title: Bad
aspectRatio: "16/9"
canvasWidth: 980
---

# Hi

---
layout: not-a-real-layout
---

# Broken
"""
        )
        code, output = run("audit", "bad-deck", "--workspace-root", str(self.root))
        self.assertEqual(code, 1, output)
        self.assertIn("unknown layout", output)

    def test_unknown_lucide_icon_fails(self) -> None:
        self._write_deck(
            """---
theme: default
title: Bad
aspectRatio: "16/9"
canvasWidth: 980
---

# Hi

<lucide-this-icon-does-not-exist class="ok-icon" />
"""
        )
        code, output = run("audit", "bad-deck", "--workspace-root", str(self.root))
        self.assertEqual(code, 1, output)
        self.assertIn("unknown Lucide icon", output)

    def test_fonts_block_is_a_brand_violation(self) -> None:
        self._write_deck(
            """---
theme: default
title: Bad
aspectRatio: "16/9"
canvasWidth: 980
fonts:
  sans: Inter
---

# Hi
"""
        )
        code, output = run("audit", "bad-deck", "--workspace-root", str(self.root))
        self.assertEqual(code, 1, output)
        self.assertIn("fonts:", output)

    def test_missing_style_import_fails(self) -> None:
        self._write_deck(
            """---
theme: default
title: Bad
aspectRatio: "16/9"
canvasWidth: 980
---

# Hi
""",
            style='@import "./styles/missing.css";\n',
        )
        code, output = run("audit", "bad-deck", "--workspace-root", str(self.root))
        self.assertEqual(code, 1, output)
        self.assertIn("imports missing file", output)

    def test_unbalanced_html_fails(self) -> None:
        self._write_deck(
            """---
theme: default
title: Bad
aspectRatio: "16/9"
canvasWidth: 980
---

# Hi

<div class="ok-hero">
  <p>forgot to close
"""
        )
        code, output = run("audit", "bad-deck", "--workspace-root", str(self.root))
        self.assertEqual(code, 1, output)
        self.assertIn("unclosed", output)

    def test_bare_bullets_warn(self) -> None:
        self._write_deck(
            """---
theme: default
title: Warn
aspectRatio: "16/9"
canvasWidth: 980
---

# Only Bullets

- one
- two
- three
"""
        )
        code, output = run("audit", "bad-deck", "--workspace-root", str(self.root))
        self.assertEqual(code, 0, output)
        self.assertIn("heading + bullets", output)

    def test_dev_log_errors_surface_as_audit_warnings(self) -> None:
        dest = self._write_deck(
            """---
theme: default
title: Log
aspectRatio: "16/9"
canvasWidth: 980
colorSchema: light
---

# Hi

<lucide-eye class="ok-icon" />
"""
        )
        (dest / deck.LOGFILE_NAME).write_text(
            "[vite] (client) [console.error] Failed to patch FloatingVue TypeError: x\n" * 3,
            encoding="utf-8",
        )
        code, output = run("audit", "bad-deck", "--workspace-root", str(self.root))
        self.assertEqual(code, 0, output)
        self.assertEqual(output.count("Failed to patch FloatingVue"), 1)
        self.assertIn("dev log:", output)

    def test_auto_color_scheme_warns(self) -> None:
        self._write_deck(
            """---
theme: default
title: Warn
aspectRatio: "16/9"
canvasWidth: 980
---

# Hi

<lucide-eye class="ok-icon" />
"""
        )
        code, output = run("audit", "bad-deck", "--workspace-root", str(self.root))
        self.assertEqual(code, 0, output)
        self.assertIn("colorSchema", output)

    def test_missing_required_headmatter_fails(self) -> None:
        self._write_deck(
            """---
theme: default
---

# Hi
"""
        )
        code, output = run("audit", "bad-deck", "--workspace-root", str(self.root))
        self.assertEqual(code, 1, output)
        self.assertIn("missing required key", output)

    def test_split_slides_handles_bare_separators(self) -> None:
        slides = deck.split_slides(
            """---
theme: default
title: X
aspectRatio: "16/9"
canvasWidth: 980
---

# One

---

# Two

---
layout: end
---

# Three
"""
        )
        self.assertEqual(len(slides), 3)
        self.assertEqual(slides[1].frontmatter, {})
        self.assertIn("# Two", slides[1].body)
        self.assertEqual(slides[2].frontmatter.get("layout"), "end")


if __name__ == "__main__":
    unittest.main()
