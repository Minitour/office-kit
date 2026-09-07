from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Documents are written in one pass in primary context, so they have no
# subagent. Decks and video keep their staged roster.
EXPECTED_AGENTS = {
    "brand-agent",
    "research-agent",
    "plan-agent",
    "slides-agent",
    "video-agent",
    "review-agent",
    "delivery-agent",
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

    def test_builder_agents_require_an_approved_plan(self) -> None:
        capabilities = read(ROOT / "capabilities.yaml")
        for agent in ("slides-agent", "video-agent"):
            start = capabilities.index(f"  - id: {agent}")
            next_agent = capabilities.find("\n  - id: ", start + 1)
            section = capabilities[start : next_agent if next_agent >= 0 else None]
            self.assertIn("status: approved", section, agent)
            self.assertIn("Approval gate", section, agent)

    def test_delivery_is_request_only(self) -> None:
        capabilities = read(ROOT / "capabilities.yaml")
        delivery = capabilities.split("  - id: delivery-agent", 1)[1]
        # Wrapped across lines in the YAML block, so match on whitespace.
        self.assertRegex(delivery, r"explicit\s+user\s+request")
        self.assertRegex(delivery, r"ready\s+to\s+deliver")

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
            r"|doc-agent|intake-agent|BRIEF\.md|document_port|document_root",
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
        self.assertIn("one pass", skill)

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


if __name__ == "__main__":
    unittest.main()
