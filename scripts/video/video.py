#!/usr/bin/env python3
"""Scaffold an OfficeKit HyperFrames video from the video template.

Fills Jinja templates (``*.j2``) with the project's brand and the values in
``config.toml`` ``[video]``, then copies ``brands/<id>/`` into the
project-local ``brand/`` snapshot HyperFrames can serve. Does not start a
preview, install npm packages, or write ``plan/PLAN.md``.

Usage:
    uv run python scripts/video/video.py new explainer --title "Product tour"
    uv run python scripts/video/video.py refresh explainer
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


def _snapshot_settings(root: Path) -> tuple[str, list[str], list[str]]:
    config = _common.load_config(root)
    snap = (config.get("video") or {}).get("brand_snapshot") or {}
    target = str(snap.get("target_dir") or "brand")
    files = list(snap.get("files") or ["tokens.css", "frame.md"])
    directories = list(snap.get("directories") or ["assets"])
    return target, files, directories


def context_for(
    root: Path,
    *,
    slug: str,
    brand_id: str,
    title: str,
    duration: float,
) -> dict:
    config = _common.load_config(root)
    video = config.get("video") or {}
    preview = config.get("preview") or {}
    width = int(video.get("width") or 1920)
    height = int(video.get("height") or 1080)
    return {
        "slug": slug,
        "title": title,
        "brand_id": brand_id,
        "brand_name": _common.brand_name(root, brand_id),
        "logo_rel": _common.brand_logo_rel(root, brand_id),
        "width": width,
        "height": height,
        "fps": int(video.get("fps") or 30),
        "duration": duration,
        "format": video.get("format") or "mp4",
        "output_dir": video.get("output_dir") or "renders",
        "composition": video.get("composition") or "index.html",
        "preview_port": int(preview.get("video_port") or 3002),
    }


def _apply_snapshot(root: Path, dest: Path, brand_id: str) -> Path:
    target_dir, files, directories = _snapshot_settings(root)
    return _common.snapshot_brand(
        root,
        dest,
        brand_id,
        files=files,
        directories=directories,
        target_dir=target_dir,
    )


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
        duration=args.duration,
    )
    dest.mkdir(parents=True, exist_ok=True)
    written = _common.copy_template_tree(template, dest, ctx)
    snap = _apply_snapshot(root, dest, brand_id)
    rel = _common.relative_to(dest, root)
    print(f"Created {rel} ({len(written)} file(s), brand {brand_id})")
    print(f"  snapshot: {_common.relative_to(snap, root)}")
    print(f"  next:  npm install -w {rel}")
    print(f"  next:  npx hyperframes preview --port {ctx['preview_port']}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    given = args.project.expanduser()
    dest = given.resolve() if given.is_dir() else _common.project_dir(
        root, _common.require_slug(given.as_posix())
    )
    if not dest.is_dir():
        raise ScaffoldError(f"project does not exist: {dest}")
    root = _workspace_root(args.workspace_root, dest)
    brand_id = _common.resolve_brand_id(root, args.brand)
    snap = _apply_snapshot(root, dest, brand_id)
    print(f"Refreshed {_common.relative_to(snap, root)} from brands/{brand_id}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold a HyperFrames video from .templates/video."
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
    new.add_argument("--title", default=None, help="composition title (default: the slug)")
    new.add_argument("--brand", default=None, help="brand id under brands/")
    new.add_argument("--duration", type=float, default=5.0, help="root duration in seconds")
    new.add_argument("--template", default="video", help="directory under .templates/")
    new.add_argument("--force", action="store_true", help="replace an existing scaffold")
    new.set_defaults(handler=cmd_new)

    refresh = sub.add_parser(
        "refresh", parents=[common], help="re-copy the brand snapshot into a project"
    )
    refresh.add_argument("project", type=Path, help="project directory or slug")
    refresh.add_argument("--brand", default=None, help="brand id under brands/")
    refresh.set_defaults(handler=cmd_refresh)
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
