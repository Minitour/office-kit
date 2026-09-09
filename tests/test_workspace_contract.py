from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Authoring stays in primary context so the conversation prefix stays warm.
# Research is the only production subagent; brand-agent owns identity writes.
EXPECTED_AGENTS = {
    "brand-agent",
    "research-agent",
}
ROUTERS = (
    ROOT / "WORKFLOW.md",
    ROOT / "skills/create-doc/SKILL.md",
    ROOT / "skills/create-slides/SKILL.md",
    ROOT / "skills/create-video/SKILL.md",
    ROOT / "skills/init-brand/SKILL.md",
)
DOC_SKILL = ROOT / "skills/create-doc/SKILL.md"
DOC_TEMPLATE = ROOT / ".templates/document-html/document.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class WorkspaceContractTests(unittest.TestCase):
    def test_all_declared_agent_references_resolve(self) -> None:
        capabilities = read(ROOT / "capabilities.yaml")
        subagents = capabilities.split("\nsubagents:\n", 1)[1]
        declared = set(re.findall(r"^  - id: ([a-z-]+-agent)$", subagents, re.MULTILINE))
        self.assertEqual(declared, EXPECTED_AGENTS)

        referenced: set[str] = set()
        for path in ROUTERS:
            referenced.update(re.findall(r"`([a-z-]+-agent)`", read(path)))
        self.assertLessEqual(referenced, declared)

    def test_decks_and_video_are_authored_in_primary_context(self) -> None:
        """A subagent would drop the prefix. Research is the only spawn."""
        capabilities = read(ROOT / "capabilities.yaml")
        for retired in (
            "plan-agent",
            "slides-agent",
            "video-agent",
            "review-agent",
            "delivery-agent",
        ):
            self.assertNotIn(f"  - id: {retired}", capabilities, retired)

        for path in (
            ROOT / "WORKFLOW.md",
            ROOT / "skills/create-slides/SKILL.md",
            ROOT / "skills/create-video/SKILL.md",
        ):
            text = read(path)
            self.assertNotIn("wait for explicit approval", text, path.name)
            self.assertNotIn("status: draft", text, path.name)
            self.assertNotIn("status: approved", text, path.name)
            for retired in (
                "plan-agent",
                "slides-agent",
                "video-agent",
                "review-agent",
                "delivery-agent",
            ):
                self.assertNotIn(retired, text, f"{path.name} still names {retired}")

        slides = read(ROOT / "skills/create-slides/SKILL.md")
        video = read(ROOT / "skills/create-video/SKILL.md")
        self.assertIn("Author in the\nmain agent", slides)
        self.assertIn("Author the\nvideo in the main agent", video)
        self.assertIn("Research claims directly", slides)
        self.assertIn("Research factual claims\ndirectly", video)
        self.assertIn("two-cols-header", slides)
        self.assertIn("scripts/presentation/deck.py", slides)
        self.assertIn("scripts/video/video.py", video)
        self.assertIn("tell the user the url", slides.lower())
        self.assertIn("deck.py audit", slides)
        self.assertIn("node_modules", slides)
        self.assertIn("Lucide", slides)
        self.assertIn("PLAN.md", slides)

        brand_start = capabilities.index("  - id: brand-agent")
        brand_next = capabilities.find("\n  - id: ", brand_start + 1)
        brand = capabilities[brand_start : brand_next if brand_next >= 0 else None]
        self.assertIn("Approval gate", brand)

    def test_delivery_is_request_only(self) -> None:
        slides = read(ROOT / "skills/create-slides/SKILL.md")
        video = read(ROOT / "skills/create-video/SKILL.md")
        self.assertIn("Export only when requested", slides)
        self.assertIn("Render only when the user names", video)

    def test_legacy_contracts_are_absent(self) -> None:
        checked = [
            ROOT / "README.md",
            ROOT / "WORKFLOW.md",
            ROOT / "capabilities.yaml",
            ROOT / "config.toml",
            *ROUTERS[1:],
        ]
        legacy = re.compile(
            r"quarto|_brand\.yml|create-docs|planning-agent|document-agent"
            # Retired by the one-pass document pipeline.
            r"|doc-agent|intake-agent|BRIEF\.md|document_port|document_root"
            r"|slides-agent|video-agent|plan-agent|review-agent|delivery-agent",
            re.IGNORECASE,
        )
        for path in checked:
            self.assertIsNone(legacy.search(read(path)), str(path))


class DocumentPipelineContractTests(unittest.TestCase):
    """The document path has to stay direct, single-file, and server-free."""

    def test_document_template_is_one_self_contained_file(self) -> None:
        files = sorted(
            path.name
            for path in DOC_TEMPLATE.parent.rglob("*")
            if path.is_file()
        )
        self.assertEqual(files, ["document.html"])

        template = read(DOC_TEMPLATE)
        self.assertNotIn("<link rel=\"stylesheet\"", template)
        self.assertNotRegex(template, r"<script[^>]*\ssrc=")
        # Brand values arrive through the script-owned region, never by hand.
        self.assertIn("/* officekit:brand:start */", template)
        self.assertIn("/* officekit:brand:end */", template)
        self.assertIn("<!-- officekit:content -->", template)
        self.assertIn("<!-- officekit:toc:start -->", template)

    def test_template_keeps_the_settled_layout_rules(self) -> None:
        """These were each paid for by a review cycle; they must not regress."""
        template = read(DOC_TEMPLATE)
        # A heading landing flush against the top of the viewport.
        self.assertIn("scroll-padding-top", template)
        # Baseline accessibility and print behaviour.
        self.assertIn("skip-link", template)
        self.assertIn("prefers-reduced-motion", template)
        self.assertIn("@media print", template)

    def test_contents_are_a_side_rail_not_a_band_across_the_document(self) -> None:
        """A panel stuck to the top of the viewport costs the reader a screen."""
        template = read(DOC_TEMPLATE)
        self.assertIn("@media (min-width: 64rem)", template)
        self.assertIn("grid-template-columns: var(--doc-rail)", template)
        # The rail scrolls inside itself rather than capping at a slice of the
        # viewport, which is what the old top band did.
        self.assertIn("max-height: 100vh", template)
        self.assertNotIn("max-height: min(40vh, 18rem)", template)
        # Dropped when the rail arrived; a leftover would mean dead measuring JS.
        self.assertNotIn("--doc-toc-height", template)
        # Closed <details> hide their slot; the rail has to force that slot
        # open or a trip through a narrow viewport leaves it empty.
        self.assertIn("::details-content", template)
        self.assertIn("content-visibility: visible", template)
        # Crossing back to the rail must set open, not trust a CSS override.
        self.assertIn("setTocOpen(true)", template)
        self.assertNotIn("if (!tocDetails || tocToggledByUser) return;", template)

    def test_the_template_owns_refreshable_regions(self) -> None:
        """A self-contained document can only take a template fix through these."""
        template = read(DOC_TEMPLATE)
        for marker in (
            "/* officekit:styles:start */",
            "/* officekit:script:start */",
            "/* officekit:script:end */",
        ):
            self.assertIn(marker, template)

    def test_document_skill_is_direct_and_serverless(self) -> None:
        skill = read(DOC_SKILL)
        # Machinery the document path must never reach for. These strings
        # cannot appear in a prohibition, so they only match real instructions.
        for forbidden in (
            "http.server",
            "127.0.0.1",
            "localhost",
            "--port",
            "package.py",
            "doc-agent",
            "intake-agent",
            "status: approved",
        ):
            self.assertNotIn(forbidden, skill, forbidden)
        # It must name the pipeline it actually drives.
        for command in ("doc.py new", "doc.py toc", "doc.py check", "NOTES.md"):
            self.assertIn(command, skill, command)
        self.assertIn("one file", skill)

    def test_workflow_sends_documents_straight_through(self) -> None:
        workflow = read(ROOT / "WORKFLOW.md")
        self.assertIn("Documents are direct", workflow)
        self.assertIn("scripts/document/doc.py", workflow)

    def test_config_document_template_matches_the_scaffolder(self) -> None:
        config = read(ROOT / "config.toml")
        section = config.split("[document]", 1)[1].split("\n[", 1)[0]
        configured = re.search(r'template\s*=\s*"([^"]+)"', section)
        self.assertIsNotNone(configured)

        scaffolder = read(ROOT / "scripts/document/doc.py")
        default = re.search(r'DEFAULT_TEMPLATE\s*=\s*"([^"]+)"', scaffolder)
        self.assertIsNotNone(default)
        self.assertEqual(configured.group(1), default.group(1))

    def test_no_document_preview_port_is_configured(self) -> None:
        config = read(ROOT / "config.toml")
        preview = config.split("[preview]", 1)[1]
        self.assertNotIn("document", preview)

    def test_brands_live_in_a_named_catalog(self) -> None:
        self.assertTrue((ROOT / "brands" / "officekit" / "brand.json").is_file())
        self.assertFalse((ROOT / "brand").exists())
        config = read(ROOT / "config.toml")
        assigned = re.search(r'^\[brand\]\s*^default\s*=\s*"([^"]+)"', config, re.M)
        self.assertIsNotNone(assigned)
        self.assertEqual(assigned.group(1), "officekit")
        slides = read(ROOT / ".templates" / "presentation" / "style.css.j2")
        self.assertIn("../../brands/{{ brand_id }}/tokens.css", slides)


class SkillInvocationContractTests(unittest.TestCase):
    """Skills run Python through the workspace uv env, never a bare interpreter."""

    def test_skills_invoke_python_through_uv(self) -> None:
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            hits = [
                line.strip()
                for line in read(path).splitlines()
                if re.search(r"\bpython(?:3)?\s", line)
                and "uv run" not in line
                and not line.lstrip().startswith("#!")
            ]
            self.assertEqual(hits, [], f"{path.relative_to(ROOT)} still calls python directly")


if __name__ == "__main__":
    unittest.main()
