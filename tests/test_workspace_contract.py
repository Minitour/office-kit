from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_AGENTS = {
    "brand-agent",
    "intake-agent",
    "research-agent",
    "plan-agent",
    "doc-agent",
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


class WorkspaceContractTests(unittest.TestCase):
    def test_all_declared_agent_references_resolve(self) -> None:
        capabilities = (ROOT / "capabilities.yaml").read_text(encoding="utf-8")
        subagents = capabilities.split("\nsubagents:\n", 1)[1]
        declared = set(re.findall(r"^  - id: ([a-z-]+-agent)$", subagents, re.MULTILINE))
        self.assertEqual(declared, EXPECTED_AGENTS)

        referenced: set[str] = set()
        for path in ROUTERS:
            referenced.update(
                re.findall(r"`([a-z-]+-agent)`", path.read_text(encoding="utf-8"))
            )
        self.assertLessEqual(referenced, declared)

    def test_builder_agents_require_an_approved_plan(self) -> None:
        capabilities = (ROOT / "capabilities.yaml").read_text(encoding="utf-8")
        for agent in ("doc-agent", "slides-agent", "video-agent"):
            start = capabilities.index(f"  - id: {agent}")
            next_agent = capabilities.find("\n  - id: ", start + 1)
            section = capabilities[start : next_agent if next_agent >= 0 else None]
            self.assertIn("status: approved", section, agent)
            self.assertIn("Approval gate", section, agent)

    def test_delivery_is_request_only(self) -> None:
        capabilities = (ROOT / "capabilities.yaml").read_text(encoding="utf-8")
        delivery = capabilities.split("  - id: delivery-agent", 1)[1]
        self.assertIn("explicit user request", delivery)
        self.assertIn("ready to deliver", delivery)

    def test_legacy_quarto_contract_is_absent(self) -> None:
        checked = [
            ROOT / "README.md",
            ROOT / "WORKFLOW.md",
            ROOT / "capabilities.yaml",
            ROOT / "config.toml",
            *ROUTERS[1:],
        ]
        legacy = re.compile(r"quarto|_brand\.yml|create-docs|planning-agent|document-agent", re.I)
        for path in checked:
            self.assertIsNone(legacy.search(path.read_text(encoding="utf-8")), str(path))


if __name__ == "__main__":
    unittest.main()
