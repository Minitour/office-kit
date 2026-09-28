#!/usr/bin/env python3
"""Scaffold, render, audit, and refresh OfficeKit motion reels.

A motion reel is a canvas page whose ``seek(t)`` paints any frame as a pure
function of time, a ``timeline.js`` beat grid that picture and sound both read,
and a ``score.mjs`` that synthesizes the soundtrack from that grid. This CLI
fills the Jinja templates from ``config.toml`` ``[motion]`` and the brand,
snapshots ``brands/<id>/`` into the project-local ``brand/``, and drives
``scripts/motion/render.mjs`` (headless Chromium + ffmpeg) so agents never
improvise a render loop.

Usage:
    uv run python scripts/motion/reel.py new launch --title "Launch reel"
    uv run python scripts/motion/reel.py stills launch [--times 1.2,6,11] [--format vertical]
    uv run python scripts/motion/reel.py animatic launch
    uv run python scripts/motion/reel.py audit launch
    uv run python scripts/motion/reel.py render launch [--format vertical]
    uv run python scripts/motion/reel.py poster launch
    uv run python scripts/motion/reel.py refresh launch
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import wave
from array import array
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

FORMATS = ("landscape", "vertical", "square")
DRIVER = Path(__file__).resolve().with_name("render.mjs")
REQUIRED = ("index.html", "timeline.js", "score.mjs", "package.json")
# seek(t) must be a pure function of t. These read a clock, draw randomness,
# or schedule work between frames, so a render would differ run to run.
IMPURE = re.compile(
    r"\b(?:Date\.now|new Date\(\)|performance\.now|Math\.random|"
    r"requestAnimationFrame|setTimeout|setInterval)\b"
)
PEAK_CEILING = 0.99  # linear; score.mjs normalises to about 0.79


def _workspace_root(explicit: Path | None, start: Path) -> Path:
    if explicit is not None:
        root = explicit.expanduser().resolve()
        if not _common.is_workspace_root(root):
            raise ScaffoldError(f"{root} is not an OfficeKit workspace")
        return root
    return _common.find_workspace_root(start)


def _motion_config(root: Path) -> dict:
    return _common.load_config(root).get("motion") or {}


def _snapshot_settings(root: Path) -> tuple[str, list[str], list[str]]:
    snap = _motion_config(root).get("brand_snapshot") or {}
    target = str(snap.get("target_dir") or "brand")
    files = list(snap.get("files") or ["tokens.css"])
    directories = list(snap.get("directories") or ["assets"])
    return target, files, directories


def _brand_url(root: Path, brand_id: str) -> str:
    path = _common.brand_dir(root, brand_id) / "brand.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str((data.get("meta") or {}).get("url") or "").strip()


def context_for(
    root: Path,
    *,
    slug: str,
    brand_id: str,
    title: str,
    duration: float,
) -> dict:
    motion = _motion_config(root)
    return {
        "slug": slug,
        "title": title,
        "brand_id": brand_id,
        "brand_name": _common.brand_name(root, brand_id),
        "brand_url": _brand_url(root, brand_id),
        "logo_rel": _common.brand_logo_rel(root, brand_id),
        "width": int(motion.get("width") or 1920),
        "height": int(motion.get("height") or 1080),
        "fps": int(motion.get("fps") or 60),
        "duration": duration,
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
        slug = dest.name
    else:
        slug = _common.require_slug(slug_or_path)
        dest = _common.project_dir(root, slug)
    if not dest.is_dir():
        raise ScaffoldError(f"project does not exist: {_common.relative_to(dest, root)}")
    for name in ("index.html", "timeline.js"):
        if not (dest / name).is_file():
            raise ScaffoldError(
                f"{_common.relative_to(dest, root)}/{name} is missing; "
                "scaffold with `reel.py new` first"
            )
    return slug, dest


def _formats(root: Path, requested: str | None) -> list[str]:
    if requested:
        return [requested]
    configured = [str(f) for f in (_motion_config(root).get("formats") or ["landscape"])]
    unknown = [f for f in configured if f not in FORMATS]
    if unknown:
        raise ScaffoldError(f"config.toml [motion] formats has unknown {unknown}; use {FORMATS}")
    return configured


def _drive(root: Path, dest: Path, mode: str, *extra: str, fmt: str = "landscape") -> int:
    output_dir = str(_motion_config(root).get("output_dir") or "renders")
    command = [
        _common.node_bin("node"),
        str(DRIVER),
        str(dest),
        mode,
        *extra,
        f"--format={fmt}",
        f"--output-dir={output_dir}",
    ]
    shown = " ".join(["node scripts/motion/render.mjs", _common.relative_to(dest, root), mode, *extra])
    print(f"  run:   {shown} --format={fmt}", flush=True)
    return subprocess.run(command, cwd=root, check=False).returncode


def _wav_peak(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        if handle.getsampwidth() != 2:
            raise ScaffoldError(f"{path} is not 16-bit PCM")
        samples = array("h", handle.readframes(handle.getnframes()))
    if sys.byteorder == "big":  # pragma: no cover
        samples.byteswap()
    return max((abs(s) for s in samples), default=0) / 32767


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
    template_name = args.template or str(_motion_config(root).get("template") or "motion")
    template = root / ".templates" / template_name
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

    print(f"  next:  uv run python scripts/motion/reel.py stills {slug}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    _, dest = _resolve_project(root, str(args.project))
    brand_id = _common.resolve_brand_id(root, args.brand)
    snap = _apply_snapshot(root, dest, brand_id)
    print(f"Refreshed {_common.relative_to(snap, root)} from brands/{brand_id}")
    return 0


def cmd_stills(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    _, dest = _resolve_project(root, args.slug)
    extra = [args.times] if args.times else []
    failures = sum(
        _drive(root, dest, "stills", *extra, fmt=fmt) != 0
        for fmt in _formats(root, args.format)
    )
    return 1 if failures else 0


def cmd_animatic(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    _, dest = _resolve_project(root, args.slug)
    return 1 if _drive(root, dest, "animatic", fmt=args.format or "landscape") else 0


def cmd_poster(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    _, dest = _resolve_project(root, args.slug)
    extra = [str(args.time)] if args.time is not None else []
    return 1 if _drive(root, dest, "poster", *extra, fmt=args.format or "landscape") else 0


def cmd_render(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    _, dest = _resolve_project(root, args.slug)
    extra = [str(args.fps)] if args.fps else []
    failures = sum(
        _drive(root, dest, "video", *extra, fmt=fmt) != 0
        for fmt in _formats(root, args.format)
    )
    return 1 if failures else 0


def cmd_audit(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    _, dest = _resolve_project(root, args.slug)
    rel = _common.relative_to(dest, root)
    failures = 0

    for name in REQUIRED:
        if not (dest / name).is_file():
            print(f"  error: {name} missing")
            failures += 1
    if not (dest / "brand" / "tokens.css").is_file():
        print("  error: brand/tokens.css missing; run `reel.py refresh`")
        failures += 1

    for name in ("index.html", "timeline.js"):
        path = dest / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            hit = IMPURE.search(line)
            if hit:
                print(f"  error: {name}:{number} uses {hit.group(0)}; seek(t) must depend on t only")
                failures += 1
        if "\u2014" in text:
            print(f"  error: {name} contains an em dash; use a full stop, colon or two lines")
            failures += 1

    if args.skip_render:
        print("  skip:  score + determinism (--skip-render)")
    else:
        node = _common.node_bin("node")
        if subprocess.run([node, str(dest / "score.mjs")], cwd=dest, check=False).returncode:
            print("  error: score.mjs failed")
            failures += 1
        else:
            peak = _wav_peak(dest / "media" / "score.wav")
            print(f"  score: media/score.wav peak {peak:.2f} of full scale")
            if peak >= PEAK_CEILING:
                print("  error: score clips; lower the master gain in score.mjs")
                failures += 1
        for fmt in _formats(root, args.format):
            if _drive(root, dest, "verify", fmt=fmt) != 0:
                failures += 1

    if failures:
        print(f"FAIL {rel}: {failures} check(s) failed")
        return 1
    print(f"PASS {rel}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold, render, and audit a code-drawn motion reel."
    )
    root_help = "workspace root (default: nearest parent holding config.toml or brands/)"
    parser.add_argument("--workspace-root", type=Path, default=None, help=root_help)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--workspace-root", type=Path, default=argparse.SUPPRESS, help=root_help
    )
    fmt = argparse.ArgumentParser(add_help=False)
    fmt.add_argument(
        "--format",
        choices=FORMATS,
        default=None,
        help="one format (default: config.toml [motion] formats, or landscape)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", parents=[common], help="create projects/<slug>/")
    new.add_argument("slug", help="project slug: lowercase letters, digits, hyphens")
    new.add_argument("--title", default=None, help="reel title (default: the slug)")
    new.add_argument("--brand", default=None, help="brand id under brands/")
    new.add_argument("--duration", type=float, default=7.5, help="length in seconds")
    new.add_argument("--template", default=None, help="directory under .templates/")
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

    stills = sub.add_parser(
        "stills", parents=[common, fmt], help="PNG stills + contact sheet in reports/stills/"
    )
    stills.add_argument("slug", help="project slug or path under projects/")
    stills.add_argument("--times", default=None, help="comma-separated seconds (default: 20 spread)")
    stills.set_defaults(handler=cmd_stills)

    animatic = sub.add_parser(
        "animatic", parents=[common, fmt], help="12 fps draft MP4 with the score, for timing"
    )
    animatic.add_argument("slug", help="project slug or path under projects/")
    animatic.set_defaults(handler=cmd_animatic)

    audit = sub.add_parser(
        "audit", parents=[common, fmt], help="static checks, score peak, determinism"
    )
    audit.add_argument("slug", help="project slug or path under projects/")
    audit.add_argument(
        "--skip-render", action="store_true", help="static checks only (no node, no browser)"
    )
    audit.set_defaults(handler=cmd_audit)

    render = sub.add_parser(
        "render", parents=[common, fmt], help="final MP4 with the score, into renders/"
    )
    render.add_argument("slug", help="project slug or path under projects/")
    render.add_argument("--fps", type=int, default=None, help="override timeline fps")
    render.set_defaults(handler=cmd_render)

    poster = sub.add_parser(
        "poster", parents=[common, fmt], help="one full-resolution PNG into renders/"
    )
    poster.add_argument("slug", help="project slug or path under projects/")
    poster.add_argument("--time", type=float, default=None, help="seconds (default: after the tagline)")
    poster.set_defaults(handler=cmd_poster)
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
