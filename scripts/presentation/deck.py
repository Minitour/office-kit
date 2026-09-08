#!/usr/bin/env python3
"""Scaffold an OfficeKit Slidev deck from the presentation template.

Fills Jinja templates (``*.j2``) with the project's brand, the values in
``config.toml`` ``[presentation]``, and the title/author you pass. Does not
start a preview server, install npm packages, or write ``plan/PLAN.md``.

Usage:
    uv run python scripts/presentation/deck.py new kickoff --title "Q3 Kickoff"
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Sequence


def _load_common():
    path = Path(__file__).resolve().parents[1] / "common.py"
    spec = importlib.util.spec_from_file_location("officekit_common", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_common = _load_common()
ScaffoldError = _common.ScaffoldError


def _workspace_root(explicit: Path | None, start: Path) -> Path:
    if explicit is not None:
        root = explicit.expanduser().resolve()
        if not _common.is_workspace_root(root):
            raise ScaffoldError(f"{root} is not an OfficeKit workspace")
        return root
    return _common.find_workspace_root(start)


def context_for(root: Path, *, slug: str, brand_id: str, title: str, author: str | None) -> dict:
    config = _common.load_config(root)
    presentation = config.get("presentation") or {}
    preview = config.get("preview") or {}
    export = presentation.get("export") or {}
    export_format = str(export.get("format") or "pdf")
    return {
        "slug": slug,
        "title": title,
        "author": author or _common.brand_name(root, brand_id),
        "brand_id": brand_id,
        "brand_name": _common.brand_name(root, brand_id),
        "logo_rel": _common.brand_logo_rel(root, brand_id),
        "theme": presentation.get("theme") or "default",
        "aspect_ratio": presentation.get("aspect_ratio") or "16/9",
        "canvas_width": int(presentation.get("canvas_width") or 980),
        "preview_port": int(preview.get("presentation_port") or 3030),
        "export_dir": export.get("output_dir") or "dist",
        "export_format": export_format,
        "export_ext": "png" if export_format == "png" else export_format,
    }


def cmd_new(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    slug = _common.require_slug(args.slug)
    brand_id = _common.resolve_brand_id(root, args.brand)
    dest = _common.project_dir(root, slug)
    if dest.exists() and any(dest.iterdir()) and not args.force:
        raise ScaffoldError(
            f"{_common.relative_to(dest, root)} already exists; "
            "edit it, or pass --force to replace the scaffold"
        )

    template = root / ".templates" / args.template
    ctx = context_for(
        root,
        slug=slug,
        brand_id=brand_id,
        title=args.title or slug.replace("-", " ").title(),
        author=args.author,
    )
    dest.mkdir(parents=True, exist_ok=True)
    written = _common.copy_template_tree(template, dest, ctx)
    rel = _common.relative_to(dest, root)
    print(f"Created {rel} ({len(written)} file(s), brand {brand_id})")
    print(f"  next:  npm install -w {rel}")
    print(f"  next:  npx slidev --port {ctx['preview_port']}")
    print(f"  open:  http://localhost:{ctx['preview_port']}/")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold a Slidev deck from .templates/presentation."
    )
    root_help = "workspace root (default: nearest parent holding config.toml or brands/)"
    parser.add_argument("--workspace-root", type=Path, default=None, help=root_help)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--workspace-root", type=Path, default=argparse.SUPPRESS, help=root_help
    )
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", parents=[common], help="create projects/<slug>/")
    new.add_argument("slug", help="project slug: lowercase letters, digits, hyphens")
    new.add_argument("--title", default=None, help="deck title (default: the slug)")
    new.add_argument("--author", default=None, help="byline (default: the brand name)")
    new.add_argument("--brand", default=None, help="brand id under brands/")
    new.add_argument(
        "--template",
        default="presentation",
        help="directory under .templates/",
    )
    new.add_argument("--force", action="store_true", help="replace an existing scaffold")
    new.set_defaults(handler=cmd_new)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (ScaffoldError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
