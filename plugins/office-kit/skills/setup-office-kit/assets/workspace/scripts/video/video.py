#!/usr/bin/env python3
"""Scaffold, preview, audit, and refresh OfficeKit HyperFrames videos.

Fills Jinja templates (``*.j2``) with the project's brand and the values in
``config.toml`` ``[video]``, then copies ``brands/<id>/`` into the
project-local ``brand/`` snapshot HyperFrames can serve. Owns the preview
lifecycle so agents never improvise ``npx hyperframes`` against the wrong cwd.

Usage:
    uv run python scripts/video/video.py new explainer --title "Product tour"
    uv run python scripts/video/video.py dev explainer
    uv run python scripts/video/video.py audit explainer
    uv run python scripts/video/video.py stop explainer
    uv run python scripts/video/video.py refresh explainer
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
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

PIDFILE_NAME = ".hyperframes-dev.pid"
LOGFILE_NAME = ".hyperframes-dev.log"
RECLAIMABLE = ("hyperframes", "vite")
HYPERFRAMES_PACKAGE = "hyperframes@0.8.30"


def _hyperframes_command(*args: str) -> list[str]:
    """``npx --yes hyperframes@<pin> …`` with npx resolved for this platform."""
    return [_common.node_bin("npx"), "--yes", HYPERFRAMES_PACKAGE, *args]


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


def _resolve_project(root: Path, slug_or_path: str) -> tuple[str, Path]:
    given = Path(slug_or_path)
    if given.is_dir() or (
        given.parts and (root / given).is_dir() and given.name != slug_or_path
    ):
        dest = given.expanduser().resolve() if given.is_absolute() else (root / given).resolve()
        if not dest.is_dir():
            raise ScaffoldError(f"project does not exist: {dest}")
        slug = dest.name
    else:
        slug = _common.require_slug(slug_or_path)
        dest = _common.project_dir(root, slug)
        if not dest.is_dir():
            raise ScaffoldError(
                f"project does not exist: {_common.relative_to(dest, root)}"
            )
    return slug, dest


def _pidfile(dest: Path) -> Path:
    return dest / PIDFILE_NAME


def _logfile(dest: Path) -> Path:
    return dest / LOGFILE_NAME


def _composition_path(root: Path, dest: Path) -> Path:
    config = _common.load_config(root)
    name = str((config.get("video") or {}).get("composition") or "index.html")
    path = dest / name
    if not path.is_file():
        raise ScaffoldError(
            f"{_common.relative_to(dest, root)}/{name} is missing; "
            "scaffold with `video.py new` first"
        )
    return path


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

    if args.no_install:
        print("  skip:  npm install (--no-install)")
    else:
        print(f"  install: npm install -w {rel}")
        _common.npm_install_workspace(root, rel)

    print(f"  next:  uv run python scripts/video/video.py dev {slug}")
    print(f"  open:  http://localhost:{ctx['preview_port']}/")
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


def cmd_dev(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    slug, dest = _resolve_project(root, args.slug)
    _composition_path(root, dest)

    config = _common.load_config(root)
    preferred = int((config.get("preview") or {}).get("video_port") or 3002)
    if args.port is not None:
        preferred = int(args.port)

    existing = _common.read_pidfile(_pidfile(dest))
    if existing.get("pid"):
        for note in _common.stop_pidfile(_pidfile(dest)):
            print(f"  {note}")

    port, notes = _common.claim_port(preferred, reclaimable=RECLAIMABLE)
    for note in notes:
        print(f"  {note}")

    log_path = _logfile(dest)
    pid = _common.spawn_detached(
        _hyperframes_command("preview", "--port", str(port)),
        cwd=dest,
        log_path=log_path,
    )
    _common.write_pidfile(_pidfile(dest), pid, port=port, slug=slug)
    url = f"http://localhost:{port}/"
    print(f"Starting HyperFrames for {slug} (pid {pid}, port {port})")
    print(f"  log:   {_common.relative_to(log_path, root)}")

    if not _common.wait_http_ok(url, timeout_seconds=args.timeout):
        raise ScaffoldError(
            f"HyperFrames did not become healthy at {url} within {args.timeout:.0f}s; "
            f"see {log_path}"
        )

    print(f"  open:  {url}")
    print(f"  stop:  uv run python scripts/video/video.py stop {slug}")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    if args.slug:
        slug, dest = _resolve_project(root, args.slug)
        notes = _common.stop_pidfile(_pidfile(dest))
        if not notes:
            print(f"No managed HyperFrames server for {slug}")
            return 0
        for note in notes:
            print(f"  {note}")
        print(f"Stopped {slug}")
        return 0

    projects = root / "projects"
    stopped = 0
    if projects.is_dir():
        for pidfile in projects.glob(f"*/{PIDFILE_NAME}"):
            for note in _common.stop_pidfile(pidfile):
                print(f"  {pidfile.parent.name}: {note}")
            stopped += 1
    if stopped == 0:
        print("No managed HyperFrames servers")
    else:
        print(f"Stopped {stopped} server(s)")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    slug, dest = _resolve_project(root, args.slug)
    _composition_path(root, dest)
    rel = _common.relative_to(dest, root)

    failures = 0
    for subcommand in ("lint", "check"):
        command = _hyperframes_command(subcommand)
        print(f"  run:   {' '.join(command)} ({rel})")
        try:
            result = subprocess.run(command, cwd=dest, check=False)
        except FileNotFoundError as exc:
            raise ScaffoldError("npx is not installed or not on PATH") from exc
        if result.returncode != 0:
            print(f"  error: hyperframes {subcommand} exited {result.returncode}")
            failures += 1

    brand_dir = dest / "brand"
    if not (brand_dir / "tokens.css").is_file():
        print("  error: brand/tokens.css missing — run `video.py refresh`")
        failures += 1

    if failures:
        print(f"FAIL {rel} — {failures} check(s) failed")
        return 1
    print(f"PASS {rel} — hyperframes lint + check")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold, preview, and audit a HyperFrames video."
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
    new.add_argument(
        "--no-install",
        action="store_true",
        help="skip npm install -w (offline / tests)",
    )
    new.set_defaults(handler=cmd_new)

    refresh = sub.add_parser(
        "refresh", parents=[common], help="re-copy the brand snapshot into a project"
    )
    refresh.add_argument("project", type=Path, help="project directory or slug")
    refresh.add_argument("--brand", default=None, help="brand id under brands/")
    refresh.set_defaults(handler=cmd_refresh)

    dev = sub.add_parser("dev", parents=[common], help="start the HyperFrames preview")
    dev.add_argument("slug", help="project slug or path under projects/")
    dev.add_argument("--port", type=int, default=None, help="override preview port")
    dev.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="seconds to wait for the preview to become healthy",
    )
    dev.set_defaults(handler=cmd_dev)

    stop = sub.add_parser(
        "stop", parents=[common], help="stop a managed HyperFrames preview"
    )
    stop.add_argument(
        "slug",
        nargs="?",
        default=None,
        help="project slug (omit to stop every managed video)",
    )
    stop.set_defaults(handler=cmd_stop)

    audit = sub.add_parser(
        "audit", parents=[common], help="run hyperframes lint + check"
    )
    audit.add_argument("slug", help="project slug or path under projects/")
    audit.set_defaults(handler=cmd_audit)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _common.configure_console()
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (ScaffoldError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
