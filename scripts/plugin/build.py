#!/usr/bin/env python3
"""Build and verify the portable OfficeKit Agent Plugin.

The plugin is intentionally assembled from an allowlist. Only OfficeKit-owned
skills, scripts, templates, and the neutral OfficeKit brand enter the package.
Third-party skills, MCP configuration, dependencies, model weights, generated
locks, and internal brands are never copied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "office-kit"
VERSION = "0.1.0"

SKILLS = (
    "setup-office-kit",
    "init-brand",
    "create-doc",
    "create-slides",
    "create-video",
    "text-to-speech",
    "strudel-offline",
)

MANIFEST = {
    "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
    "name": "office-kit",
    "version": VERSION,
    "description": (
        "Create branded standalone HTML documents, Slidev decks, and "
        "HyperFrames videos in an isolated OfficeKit workspace."
    ),
    "author": {"name": "OfficeKit"},
    "homepage": "https://github.com/Minitour/office-kit",
    "repository": "https://github.com/Minitour/office-kit",
    "keywords": [
        "documents",
        "presentations",
        "slides",
        "video",
        "branding",
        "office-kit",
    ],
}

ADAPTER_MANIFEST = {
    "name": MANIFEST["name"],
    "version": MANIFEST["version"],
    "description": MANIFEST["description"],
    "author": MANIFEST["author"],
    "homepage": MANIFEST["homepage"],
    "repository": MANIFEST["repository"],
}

CURSOR_ADAPTER_MANIFEST = {
    **ADAPTER_MANIFEST,
    "skills": "./skills/",
}

CODEX_ADAPTER_MANIFEST = {
    **ADAPTER_MANIFEST,
    "skills": "./skills/",
}

CLAUDE_MARKETPLACE = {
    "name": "office-kit",
    "description": "OfficeKit standalone skills",
    "owner": {"name": "OfficeKit"},
    "plugins": [
        {
            "name": MANIFEST["name"],
            "description": MANIFEST["description"],
            "version": VERSION,
            "source": "./plugins/office-kit",
            "author": MANIFEST["author"],
        }
    ],
}

CURSOR_MARKETPLACE = {
    "name": "office-kit",
    "owner": {"name": "OfficeKit"},
    "plugins": [
        {
            "name": MANIFEST["name"],
            "source": "./plugins/office-kit",
            "description": MANIFEST["description"],
        }
    ],
}

CODEX_MARKETPLACE = {
    "name": "office-kit",
    "interface": {"displayName": "OfficeKit"},
    "plugins": [
        {
            "name": MANIFEST["name"],
            "source": {
                "source": "url",
                "url": "./plugins/office-kit",
            },
            "policy": {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL",
            },
            "category": "Productivity",
        }
    ],
}

# Canonical workspace files copied into setup-office-kit's payload.
WORKSPACE_FILES = (
    ".gitignore",
    "config.toml",
    "package.json",
    "pyproject.toml",
    ".templates/document-html/document.html",
    ".templates/presentation/global-bottom.vue",
    ".templates/presentation/package.json.j2",
    ".templates/presentation/plan/.gitkeep",
    ".templates/presentation/public/.gitkeep",
    ".templates/presentation/public/figure-placeholder.svg",
    ".templates/presentation/layouts/.gitkeep",
    ".templates/presentation/layouts/end.vue",
    ".templates/presentation/components/.gitkeep",
    ".templates/presentation/components/OkBars.vue",
    ".templates/presentation/slides.md.j2",
    ".templates/presentation/style.css.j2",
    ".templates/presentation/styles/brand.css",
    ".templates/video/frame.md",
    ".templates/video/hyperframes.json",
    ".templates/video/index.html.j2",
    ".templates/video/package.json.j2",
    ".templates/video/brand/.gitkeep",
    ".templates/video/media/.gitkeep",
    ".templates/video/narration/.gitkeep",
    ".templates/video/plan/.gitkeep",
    "brands/officekit/BRAND.md",
    "brands/officekit/brand.json",
    "brands/officekit/frame.md",
    "brands/officekit/tokens.css",
    "brands/officekit/assets/logo-light.svg",
    "brands/officekit/assets/logo.svg",
    "scripts/common.py",
    "scripts/brand/catalog.py",
    "scripts/brand/generate.py",
    "scripts/document/doc.py",
    "scripts/document/package.py",
    "scripts/presentation/deck.py",
    "scripts/presentation/render-audit.mjs",
    "scripts/video/video.py",
)

MANUAL_PLUGIN_FILES = (
    "README.md",
    "skills/setup-office-kit/SKILL.md",
    "skills/setup-office-kit/scripts/bootstrap.py",
    "skills/init-brand/SKILL.md",
    "skills/create-doc/SKILL.md",
    "skills/create-slides/SKILL.md",
    "skills/create-video/SKILL.md",
    "skills/text-to-speech/SKILL.md",
    "skills/text-to-speech/scripts/synthesize.py",
    "skills/text-to-speech/scripts/tts_manifest.py",
    "skills/text-to-speech/voices.json",
    # Strudel/Dough music bed (AGPL-3.0-or-later; see that skill's LICENSE).
    # Its scripts/ tree carries its own npm lock so an offline render is
    # reproducible; it has no workspace dependencies.
    "skills/strudel-offline/SKILL.md",
    "skills/strudel-offline/LICENSE",
    "skills/strudel-offline/reference.md",
    "skills/strudel-offline/scripts/.gitignore",
    "skills/strudel-offline/scripts/package.json",
    "skills/strudel-offline/scripts/package-lock.json",
    "skills/strudel-offline/scripts/render.mjs",
    "skills/strudel-offline/scripts/lib.mjs",
    "skills/strudel-offline/scripts/examples/offline-safe.js",
    "skills/strudel-offline/scripts/examples/video-bed.js",
    "skills/strudel-offline/scripts/hooks/kabelsalat-stub.mjs",
    "skills/strudel-offline/scripts/hooks/register.mjs",
    "skills/strudel-offline/scripts/hooks/resolve.mjs",
    "skills/strudel-offline/scripts/vendor/dough.mjs",
)

EVAL_FILES = (
    "skills/create-doc/evals/evals.json",
    "skills/create-doc/evals/files/existing-doc/NOTES.md",
    "skills/create-doc/evals/files/existing-doc/ops-memo.html",
    "skills/create-slides/evals/evals.json",
    "skills/create-slides/evals/files/resume-approved-partial/plan/PLAN.md",
    "skills/create-slides/evals/files/resume-approved-partial/reports/build.md",
    "skills/create-slides/evals/files/resume-approved-partial/reports/research.md",
    "skills/create-video/evals/evals.json",
    "skills/create-video/evals/files/resume-approved-partial/narration/intro.wav",
    "skills/create-video/evals/files/resume-approved-partial/plan/PLAN.md",
    "skills/create-video/evals/files/resume-approved-partial/reports/build.md",
    "skills/init-brand/evals/evals.json",
    "skills/init-brand/evals/files/stale-derivatives/brand.json",
    "skills/init-brand/evals/files/stale-derivatives/tokens.css",
    "skills/strudel-offline/evals/evals.json",
    "skills/text-to-speech/evals/evals.json",
    "skills/text-to-speech/evals/files/mixed-voices.json",
    "skills/text-to-speech/evals/files/protected-clip/intro.wav",
    "skills/text-to-speech/evals/files/segments.json",
)


def _json_text(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _generated_files() -> dict[Path, bytes]:
    payload = PLUGIN / "skills" / "setup-office-kit" / "assets" / "workspace"
    workflow = (ROOT / "scripts" / "plugin" / "WORKFLOW.md").read_bytes()
    generated: dict[Path, bytes] = {
        ROOT / ".agents" / "plugins" / "marketplace.json": _json_text(
            CODEX_MARKETPLACE
        ).encode(),
        ROOT / ".claude-plugin" / "marketplace.json": _json_text(
            CLAUDE_MARKETPLACE
        ).encode(),
        ROOT / ".cursor-plugin" / "marketplace.json": _json_text(
            CURSOR_MARKETPLACE
        ).encode(),
        PLUGIN / "plugin.json": _json_text(MANIFEST).encode(),
        PLUGIN / ".claude-plugin" / "plugin.json": _json_text(
            ADAPTER_MANIFEST
        ).encode(),
        PLUGIN / ".cursor-plugin" / "plugin.json": _json_text(
            CURSOR_ADAPTER_MANIFEST
        ).encode(),
        PLUGIN / ".codex-plugin" / "plugin.json": _json_text(
            CODEX_ADAPTER_MANIFEST
        ).encode(),
        payload / "WORKFLOW.md": workflow,
        payload / "AGENTS.md": workflow,
        payload / "CLAUDE.md": workflow,
        payload / "projects" / ".gitkeep": b"\n",
    }
    for relative in WORKSPACE_FILES:
        generated[payload / relative] = (ROOT / relative).read_bytes()
    return generated


def _all_files(root: Path) -> set[Path]:
    if not root.is_dir():
        return set()
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and path.name not in {".DS_Store"}
    }


def _allowed_plugin_paths(generated: Iterable[Path]) -> set[Path]:
    allowed = {Path(path) for path in (*MANUAL_PLUGIN_FILES, *EVAL_FILES)}
    allowed.update(
        path.relative_to(PLUGIN)
        for path in generated
        if path.is_relative_to(PLUGIN)
    )
    return allowed


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build() -> int:
    generated = _generated_files()
    for path, data in generated.items():
        _write(path, data)

    allowed = _allowed_plugin_paths(generated)
    unexpected = sorted(_all_files(PLUGIN) - allowed)
    if unexpected:
        print("error: plugin contains non-allowlisted files:", file=sys.stderr)
        for path in unexpected:
            print(f"  {path.as_posix()}", file=sys.stderr)
        return 2

    print(
        f"Built {PLUGIN.relative_to(ROOT)} "
        f"({len(allowed)} files, {len(SKILLS)} OfficeKit skills)"
    )
    return 0


def check() -> int:
    generated = _generated_files()
    failures: list[str] = []
    for path, expected in generated.items():
        if not path.is_file():
            failures.append(f"missing generated file: {path.relative_to(ROOT)}")
            continue
        actual = path.read_bytes()
        if actual != expected:
            failures.append(
                f"stale generated file: {path.relative_to(ROOT)} "
                f"({_digest(actual)[:8]} != {_digest(expected)[:8]})"
            )

    allowed = _allowed_plugin_paths(generated)
    actual_paths = _all_files(PLUGIN)
    for path in sorted(actual_paths - allowed):
        failures.append(f"non-allowlisted plugin file: {path}")
    for path in sorted(allowed - actual_paths):
        failures.append(f"missing allowlisted plugin file: {path}")

    actual_skills = {
        path.parent.name
        for path in (PLUGIN / "skills").glob("*/SKILL.md")
        if path.is_file()
    }
    if actual_skills != set(SKILLS):
        failures.append(
            "skill allowlist mismatch: "
            f"expected {sorted(SKILLS)}, got {sorted(actual_skills)}"
        )

    if failures:
        for failure in failures:
            print(f"error: {failure}", file=sys.stderr)
        return 1
    print(f"PASS {PLUGIN.relative_to(ROOT)} — generated files and allowlist match")
    return 0


def _configure_console() -> None:
    """UTF-8 stdout/stderr so non-ASCII output survives a cp1252 console."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover
            pass


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated files and the package allowlist without writing",
    )
    args = parser.parse_args(argv)
    try:
        return check() if args.check else build()
    except (OSError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
