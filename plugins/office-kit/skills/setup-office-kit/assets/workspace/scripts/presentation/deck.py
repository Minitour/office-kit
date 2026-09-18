#!/usr/bin/env python3
"""Scaffold, preview, audit, and export OfficeKit Slidev decks.

Fills Jinja templates (``*.j2``) with the project's brand, the values in
``config.toml`` ``[presentation]``, and the title/author you pass. Owns the
npm workspace install and the Slidev preview lifecycle so agents never run
``npx slidev`` by hand or touch ``node_modules``.

Usage:
    uv run python scripts/presentation/deck.py new kickoff --title "Q3 Kickoff"
    uv run python scripts/presentation/deck.py dev kickoff
    uv run python scripts/presentation/deck.py audit kickoff          # static + render if a preview runs
    uv run python scripts/presentation/deck.py audit kickoff --render # start a preview if needed
    uv run python scripts/presentation/deck.py export kickoff --format pdf
    uv run python scripts/presentation/deck.py stop kickoff
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Sequence

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


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

PIDFILE_NAME = ".slidev-dev.pid"
LOGFILE_NAME = ".slidev-dev.log"
RECLAIMABLE = ("slidev", "vite")
RENDER_SCRIPT = Path(__file__).resolve().parent / "render-audit.mjs"
RENDER_DIR = Path("reports") / "render"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
LOG_ERROR_MARKERS = ("console.error", "[vite] error", "internal server error", "error:")
# Headless browsers (the render pass, export) trip these; they say nothing about the deck.
LOG_IGNORE_MARKERS = ("wake lock permission",)
LOG_TIMESTAMP_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}\s*(?:AM|PM)?\s+", re.IGNORECASE)

# Headmatter keys Slidev accepts; anything else is still allowed but we
# require the OfficeKit baseline and reject brand-breaking blocks.
REQUIRED_HEADMATTER = ("theme", "title", "aspectRatio", "canvasWidth")
KNOWN_HEADMATTER = frozenset(
    {
        "theme",
        "title",
        "info",
        "author",
        "keywords",
        "transition",
        "aspectRatio",
        "canvasWidth",
        "colorSchema",
        "layout",
        "class",
        "clicks",
        "preload",
        "recorder",
        "download",
        "exportFilename",
        "highlighter",
        "lineNumbers",
        "monaco",
        "drawings",
        "plantUmlServer",
        "fonts",
        "themeConfig",
        "css",
        "duration",
        "htmlAttrs",
        "mdc",
        "selectable",
        "favicon",
        "slidev",
    }
)

VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

LUCIDE_TAG_RE = re.compile(r"<(lucide-[a-z0-9-]+)\b", re.IGNORECASE)
IMPORT_RE = re.compile(r"""@import\s+(?:url\()?['"]([^'"]+)['"]\)?""")
LOGO_URL_RE = re.compile(r"""--ok-logo(?:-on-dark)?\s*:\s*url\(\s*['"]?([^'")]+)['"]?\s*\)""")
BULLET_RE = re.compile(r"^\s*[-*+]\s+\S", re.MULTILINE)
HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
ICON_MARK_RE = re.compile(
    r"(?:lucide-[a-z0-9-]+|class=[\"'][^\"']*\bok-(?:icon|kicker|icon-row|hero|band|step|outcome|figure|shot|split|table|code|bars))",
    re.IGNORECASE,
)
PUBLIC_SRC_RE = re.compile(r"\bsrc\s*=\s*[\"'](/[^\"'?#]*)", re.IGNORECASE)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
ALT_RE = re.compile(r"\balt\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", re.IGNORECASE)


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


def _resolve_project(root: Path, slug_or_path: str) -> tuple[str, Path]:
    given = Path(slug_or_path)
    if given.is_dir() or (given.parts and (root / given).is_dir() and given.name != slug_or_path):
        dest = given.expanduser().resolve() if given.is_absolute() else (root / given).resolve()
        if not dest.is_dir():
            raise ScaffoldError(f"project does not exist: {dest}")
        slug = dest.name
    else:
        slug = _common.require_slug(slug_or_path)
        dest = _common.project_dir(root, slug)
        if not dest.is_dir():
            raise ScaffoldError(f"project does not exist: {_common.relative_to(dest, root)}")
    return slug, dest


def _pidfile(dest: Path) -> Path:
    return dest / PIDFILE_NAME


def log_errors(text: str, *, limit: int = 3) -> list[str]:
    """Distinct error lines from a dev-server log, oldest first.

    A real error in a deck component must not drown in a plugin's repeated
    console noise, so lines are de-duplicated on their first 120 characters.
    """
    seen: set[str] = set()
    found: list[str] = []
    for raw in text.splitlines():
        line = LOG_TIMESTAMP_RE.sub("", ANSI_RE.sub("", raw).strip())
        lowered = line.lower()
        if not line or not any(marker in lowered for marker in LOG_ERROR_MARKERS):
            continue
        if any(marker in lowered for marker in LOG_IGNORE_MARKERS):
            continue
        key = line[:120]
        if key in seen:
            continue
        seen.add(key)
        found.append(line[:200])
    return found[:limit]


def _logfile(dest: Path) -> Path:
    return dest / LOGFILE_NAME


# ── new ──────────────────────────────────────────────────────────────────────


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

    if args.no_install:
        print(f"  skip:  npm install (--no-install)")
    else:
        print(f"  install: npm install -w {rel}")
        _common.npm_install_workspace(root, rel)

    print(f"  next:  uv run python scripts/presentation/deck.py dev {slug}")
    print(f"  open:  http://localhost:{ctx['preview_port']}/")
    return 0


# ── dev / stop ───────────────────────────────────────────────────────────────


def cmd_dev(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    slug, dest = _resolve_project(root, args.slug)
    slides = dest / "slides.md"
    if not slides.is_file():
        raise ScaffoldError(
            f"{_common.relative_to(dest, root)}/slides.md is missing; "
            "scaffold with `deck.py new` first — never run slidev from the workspace root"
        )

    config = _common.load_config(root)
    preferred = int((config.get("preview") or {}).get("presentation_port") or 3030)
    if args.port is not None:
        preferred = int(args.port)

    _pid, _port, url, log_path = start_preview(
        root, dest, slug, preferred=preferred, timeout=args.timeout
    )

    try:
        problems = log_errors(log_path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        problems = []
    for line in problems:
        print(f"  warn:  dev log: {line}")

    print(f"  open:  {url}")
    print(f"  stop:  uv run python scripts/presentation/deck.py stop {slug}")
    return 0


def start_preview(
    root: Path,
    dest: Path,
    slug: str,
    *,
    preferred: int,
    timeout: float,
) -> tuple[int, int, str, Path]:
    """Start (or restart) the managed Slidev preview; return pid, port, url, log."""
    # Stop a previous deck.py-managed server for this project first.
    existing = _common.read_pidfile(_pidfile(dest))
    if existing.get("pid"):
        for note in _common.stop_pidfile(_pidfile(dest)):
            print(f"  {note}")

    port, notes = _common.claim_port(preferred, reclaimable=RECLAIMABLE)
    for note in notes:
        print(f"  {note}")

    log_path = _logfile(dest)
    pid = _common.spawn_detached(
        [_common.node_bin("npx"), "slidev", "--port", str(port)],
        cwd=dest,
        log_path=log_path,
    )
    _common.write_pidfile(_pidfile(dest), pid, port=port, slug=slug)
    url = f"http://localhost:{port}/"
    print(f"Starting Slidev for {slug} (pid {pid}, port {port})")
    print(f"  log:   {_common.relative_to(log_path, root)}")

    if not _common.wait_http_ok(url, timeout_seconds=timeout):
        # Leave the process running so the log is inspectable, but fail hard.
        raise ScaffoldError(
            f"Slidev did not become healthy at {url} within {timeout:.0f}s; "
            f"see {log_path}"
        )
    return pid, port, url, log_path


def live_preview_url(dest: Path) -> str | None:
    """URL of this project's managed preview when it is up, else None."""
    data = _common.read_pidfile(_pidfile(dest))
    pid = data.get("pid") or ""
    port = data.get("port") or ""
    if not (pid.isdigit() and port.isdigit()):
        return None
    if not _common.pid_alive(int(pid)):
        return None
    url = f"http://localhost:{port}/"
    return url if _common.wait_http_ok(url, timeout_seconds=3.0) else None


def cmd_stop(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    if args.slug:
        slug, dest = _resolve_project(root, args.slug)
        notes = _common.stop_pidfile(_pidfile(dest))
        if not notes:
            print(f"No managed Slidev server for {slug}")
            return 0
        for note in notes:
            print(f"  {note}")
        print(f"Stopped {slug}")
        return 0

    # No slug: stop every managed deck under projects/.
    projects = root / "projects"
    stopped = 0
    if projects.is_dir():
        for pidfile in projects.glob(f"*/{PIDFILE_NAME}"):
            for note in _common.stop_pidfile(pidfile):
                print(f"  {pidfile.parent.name}: {note}")
            stopped += 1
    if stopped == 0:
        print("No managed Slidev servers")
    else:
        print(f"Stopped {stopped} server(s)")
    return 0


# ── audit ────────────────────────────────────────────────────────────────────


@dataclass
class Slide:
    index: int
    start_line: int
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    frontmatter_raw: str = ""
    frontmatter_error: str | None = None


@dataclass
class AuditResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    slide_count: int = 0
    headmatter: dict[str, Any] = field(default_factory=dict)
    visible_slides: int = 0
    rendered: bool = False


class _TagBalanceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in VOID_TAGS:
            return
        self.stack.append(name)

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"unexpected closing </{name}>")
            return
        if self.stack[-1] == name:
            self.stack.pop()
            return
        if name in self.stack:
            while self.stack and self.stack[-1] != name:
                missing = self.stack.pop()
                self.errors.append(f"unclosed <{missing}>")
            if self.stack and self.stack[-1] == name:
                self.stack.pop()
        else:
            self.errors.append(f"unexpected closing </{name}>")


def _parse_frontmatter_block(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return (mapping, error). Empty input is a valid empty mapping."""
    text = raw.strip("\n")
    if not text.strip():
        return {}, None
    if yaml is not None:
        try:
            data = yaml.safe_load(text)
        except Exception as exc:  # noqa: BLE001 — report parse errors as audit findings
            return None, f"YAML error: {exc}"
        if data is None:
            # Comments-only (e.g. markdown heading lines) is not frontmatter.
            return None, "frontmatter is not a YAML mapping"
        if not isinstance(data, dict):
            return None, "frontmatter must be a mapping"
        return data, None

    # Minimal fallback when PyYAML is unavailable: key: value lines only.
    data: dict[str, Any] = {}
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            return None, f"cannot parse frontmatter line without PyYAML: {line!r}"
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("\"'")
    if not data:
        return None, "frontmatter is not a YAML mapping"
    return data, None


def split_slides(text: str) -> list[Slide]:
    """Split a Slidev markdown file into slides (``---`` fences).

    A ``---`` line starts a new slide. If the lines until the next ``---``
    parse as a YAML mapping (including empty), that block is frontmatter and
    the body follows the closing fence. Otherwise the separator is bare and
    the body starts immediately — the same rules Slidev uses.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ScaffoldError("slides.md must start with a YAML frontmatter fence (---)")

    def line_is_fence(index: int) -> bool:
        return 0 <= index < len(lines) and lines[index].strip() == "---"

    def collect_until_fence(start: int) -> tuple[list[str], int, bool]:
        """Return (lines, index_of_fence_or_len, found_fence)."""
        collected: list[str] = []
        index = start
        while index < len(lines):
            if line_is_fence(index):
                return collected, index, True
            collected.append(lines[index])
            index += 1
        return collected, index, False

    slides: list[Slide] = []
    # Headmatter: opening fence at 0, FM body, closing fence required.
    fm_lines, close_at, found = collect_until_fence(1)
    if not found:
        raise ScaffoldError("unterminated frontmatter starting at line 1")
    raw_fm = "".join(fm_lines)
    data, err = _parse_frontmatter_block(raw_fm)
    body_lines, next_fence, _ = collect_until_fence(close_at + 1)
    slides.append(
        Slide(
            index=1,
            start_line=1,
            frontmatter=data or {},
            body="".join(body_lines),
            frontmatter_raw=raw_fm,
            frontmatter_error=err,
        )
    )
    cursor = next_fence

    while cursor < len(lines):
        if not line_is_fence(cursor):
            # Should not happen; append stray content to previous body.
            slides[-1].body += lines[cursor]
            cursor += 1
            continue

        start_line = cursor + 1
        peek_lines, peek_fence, peek_found = collect_until_fence(cursor + 1)
        raw_peek = "".join(peek_lines)
        peek_data, peek_err = _parse_frontmatter_block(raw_peek)
        is_frontmatter = (
            peek_found
            and peek_err is None
            and isinstance(peek_data, dict)
        )

        if is_frontmatter:
            body_lines, next_fence, _ = collect_until_fence(peek_fence + 1)
            slides.append(
                Slide(
                    index=len(slides) + 1,
                    start_line=start_line,
                    frontmatter=peek_data,
                    body="".join(body_lines),
                    frontmatter_raw=raw_peek,
                    frontmatter_error=None,
                )
            )
            cursor = next_fence
        else:
            body_lines, next_fence, _ = collect_until_fence(cursor + 1)
            slides.append(
                Slide(
                    index=len(slides) + 1,
                    start_line=start_line,
                    frontmatter={},
                    body="".join(body_lines),
                    frontmatter_raw="",
                    frontmatter_error=None,
                )
            )
            cursor = next_fence

    return slides


def discover_layouts(root: Path, dest: Path, theme: str) -> set[str]:
    names: set[str] = set()
    candidates = [
        root / "node_modules" / "@slidev" / "client" / "layouts",
        root / "node_modules" / "@slidev" / "theme-default" / "layouts",
        dest / "layouts",
    ]
    if theme and theme not in ("default", "none"):
        candidates.append(root / "node_modules" / "@slidev" / f"theme-{theme}" / "layouts")
        candidates.append(root / "node_modules" / theme / "layouts")
    for directory in candidates:
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.suffix == ".vue":
                names.add(path.stem)
    # Slidev's implicit default when layout is omitted.
    names.add("default")
    return names


def load_lucide_icons(root: Path) -> set[str]:
    path = root / "node_modules" / "@iconify-json" / "lucide" / "icons.json"
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    icons = data.get("icons") if isinstance(data, dict) else None
    if not isinstance(icons, dict):
        return set()
    names = set(icons)
    aliases = data.get("aliases")
    if isinstance(aliases, dict):
        names.update(aliases)
    return names


def _strip_css_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _check_style_imports(dest: Path, errors: list[str], warnings: list[str]) -> None:
    style = dest / "style.css"
    if not style.is_file():
        errors.append("style.css is missing")
        return
    text = _strip_css_comments(style.read_text(encoding="utf-8"))
    for match in IMPORT_RE.finditer(text):
        rel = match.group(1)
        target = (style.parent / rel).resolve()
        if not target.is_file():
            errors.append(f"style.css imports missing file: {rel}")
    for match in LOGO_URL_RE.finditer(text):
        rel = match.group(1).strip()
        if rel in ("none",) or rel.startswith(("http://", "https://", "data:")):
            continue
        target = Path(rel) if rel.startswith("/") else (style.parent / rel)
        if not target.is_file():
            # Absolute paths like /logo.svg are public/ URLs, not filesystem.
            if rel.startswith("/"):
                public = dest / "public" / rel.lstrip("/")
                if public.is_file():
                    continue
                warnings.append(
                    f"style.css --ok-logo uses public URL {rel}; "
                    "ensure the file exists under public/ or use a relative brands/ path"
                )
                continue
            errors.append(f"style.css --ok-logo path missing: {rel}")


def _check_tag_balance(body: str) -> list[str]:
    # Skip pure markdown; only scan when angle brackets look like tags.
    if "<" not in body or not re.search(r"</?[A-Za-z]", body):
        return []
    parser = _TagBalanceParser()
    try:
        parser.feed(body)
        parser.close()
    except Exception as exc:  # noqa: BLE001
        return [f"HTML parse error: {exc}"]
    findings = list(parser.errors)
    for tag in parser.stack:
        findings.append(f"unclosed <{tag}>")
    return findings


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    children: list["_Node"] = field(default_factory=list)
    text: str = ""

    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


class _TreeParser(HTMLParser):
    """Element tree of a slide body; text nodes fold into ``text``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", {})
        self.stack: list[_Node] = [self.root]

    def _open(self, tag: str, attrs) -> _Node:
        node = _Node(tag.lower(), {key: (value or "") for key, value in attrs})
        self.stack[-1].children.append(node)
        return node

    def handle_starttag(self, tag: str, attrs) -> None:
        node = self._open(tag, attrs)
        if tag.lower() not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self._open(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == name:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].text += data


def check_component_contracts(body: str) -> tuple[list[str], list[str]]:
    """Markup contracts of the ok-* components that fail silently in CSS.

    ``.ok-flow`` is a ``1fr auto 1fr auto 1fr`` grid: exactly three steps.
    ``.ok-band`` is a ``3.2rem 1fr`` grid: a mark plus one wrapper, or the
    paragraph lands in the 3.2rem column. ``.ok-hero-num`` is a text panel.
    """
    if not any(token in body for token in ("ok-flow", "ok-band", "ok-hero-num")):
        return [], []
    parser = _TreeParser()
    try:
        parser.feed(body)
        parser.close()
    except Exception:  # noqa: BLE001 - tag balance is reported elsewhere
        return [], []
    errors: list[str] = []
    warnings: list[str] = []
    for node in parser.root.walk():
        classes = node.classes()
        if "ok-flow" in classes:
            steps = [c for c in node.children if "ok-step" in c.classes()]
            joins = [c for c in node.children if "ok-flow-join" in c.classes()]
            if len(steps) != 3:
                errors.append(
                    f"ok-flow holds {len(steps)} ok-step child(ren); the grid is built "
                    "for exactly 3 (a fourth wraps and collapses every column)"
                )
            elif len(joins) != 2:
                warnings.append(
                    f"ok-flow has {len(joins)} ok-flow-join(s); expected 2, one between each step"
                )
        if "ok-band" in classes:
            if len(node.children) > 2:
                errors.append(
                    f"ok-band has {len(node.children)} element children; the 2-column grid "
                    "takes a mark plus one wrapper holding h3 + p"
                )
        if "ok-hero-num" in classes:
            odd = [c for c in node.children if c.tag not in ("span", "p")]
            has_text = bool(node.text.strip()) or any(c.text.strip() for c in node.children)
            if odd:
                warnings.append(
                    f"ok-hero-num contains <{odd[0].tag}>; it is a text panel, put the "
                    "figure in a <span> and the icon elsewhere"
                )
            elif not has_text:
                warnings.append("ok-hero-num has no text; the figure goes in a <span>")
    return errors, warnings


def check_assets(slide: Slide, dest: Path) -> tuple[list[str], list[str]]:
    """Every ``/path`` reference resolves under public/; every <img> has alt."""
    errors: list[str] = []
    warnings: list[str] = []
    public = dest / "public"
    seen: set[str] = set()

    def check_public(ref: str) -> None:
        if ref in seen or ref.startswith("//"):
            return
        seen.add(ref)
        if not (public / ref.lstrip("/")).is_file():
            errors.append(f"{ref} is not a file under public/")

    for match in PUBLIC_SRC_RE.finditer(slide.body):
        check_public(match.group(1))
    for key in ("image", "background"):
        value = slide.frontmatter.get(key)
        if isinstance(value, str) and value.startswith("/") and not value.startswith("//"):
            check_public(value.split("?", 1)[0].split("#", 1)[0])
    for match in IMG_TAG_RE.finditer(slide.body):
        alt = ALT_RE.search(match.group(0))
        if alt is None or not (alt.group(1) or alt.group(2) or "").strip():
            warnings.append(
                "<img> without alt text; describe the figure for readers who cannot see it"
            )
    return errors, warnings


def canvas_size(headmatter: dict[str, Any]) -> tuple[int, int]:
    width = int(headmatter.get("canvasWidth") or 980)
    ratio = str(headmatter.get("aspectRatio") or "16/9")
    try:
        if "/" in ratio:
            num, den = ratio.split("/", 1)
            value = float(num) / float(den)
        else:
            value = float(ratio)
    except (ValueError, ZeroDivisionError):
        value = 16 / 9
    return width, int(round(width / value))


def visible_slide_count(slides: list[Slide]) -> int:
    return sum(
        1
        for slide in slides
        if not slide.frontmatter.get("hide") and not slide.frontmatter.get("disabled")
    )


def render_findings(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Turn render-audit.mjs output into audit errors and warnings."""
    errors: list[str] = []
    warnings: list[str] = []
    scheme = str(data.get("scheme") or "light")
    prefix = "dark scheme: " if scheme == "dark" else ""
    for entry in data.get("slides") or []:
        no = entry.get("no")
        label = f"slide {no}"
        if not entry.get("found"):
            errors.append(f"{label}: {prefix}did not render (no .slidev-page-{no} element)")
            continue
        if entry.get("overflow"):
            errors.append(
                f"{label}: {prefix}content extends {entry.get('by', 0)} px past the canvas "
                f"({entry.get('element') or 'unknown element'})"
            )
        for src in entry.get("brokenImages") or []:
            errors.append(f"{label}: {prefix}image failed to load: {src}")
        if scheme == "dark" and entry.get("dark"):
            warnings.append(
                f"{label}: deck switched to Slidev's dark theme under prefers-color-scheme: dark; "
                "pin `colorSchema: light`"
            )
    return errors, warnings


def render_audit(
    root: Path,
    dest: Path,
    *,
    url: str,
    slide_count: int,
    canvas: tuple[int, int],
    out_dir: Path,
    dark: bool = False,
) -> dict[str, Any]:
    """Run render-audit.mjs against a live preview; return its JSON."""
    width, height = canvas
    command = [
        _common.node_bin("node"),
        str(RENDER_SCRIPT),
        "--base",
        url,
        "--count",
        str(slide_count),
        "--width",
        str(width),
        "--height",
        str(height),
        "--out",
        str(out_dir),
    ]
    if dark:
        command.append("--dark")
    result = subprocess.run(command, cwd=dest, check=False, capture_output=True, text=True)
    payload = (result.stdout or "").strip().splitlines()
    data: dict[str, Any] = {}
    if payload:
        try:
            data = json.loads(payload[-1])
        except json.JSONDecodeError:
            data = {}
    if result.returncode == 3 or data.get("error"):
        raise ScaffoldError(
            f"{data.get('error') or 'render audit failed'}; install it with "
            f"`npm install -w {_common.relative_to(dest, root)} playwright-chromium` "
            "from the workspace root"
        )
    if result.returncode != 0 or not isinstance(data.get("slides"), list):
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        raise ScaffoldError(
            "render audit failed"
            + (f": {detail[-1]}" if detail else f" with exit {result.returncode}")
        )
    return data


def _is_bare_bullet_slide(body: str) -> bool:
    stripped = body.strip()
    if not stripped:
        return False
    if not HEADING_RE.search(stripped):
        return False
    if not BULLET_RE.search(stripped):
        return False
    if ICON_MARK_RE.search(stripped):
        return False
    # Ignore slides that are mostly HTML structure without bullets as "bare".
    return True


def audit_deck(root: Path, dest: Path) -> AuditResult:
    result = AuditResult()
    slides_path = dest / "slides.md"
    if not slides_path.is_file():
        result.errors.append("slides.md is missing")
        return result

    text = slides_path.read_text(encoding="utf-8")
    try:
        slides = split_slides(text)
    except ScaffoldError as exc:
        result.errors.append(str(exc))
        return result

    result.slide_count = len(slides)
    result.visible_slides = visible_slide_count(slides)
    if not slides:
        result.errors.append("slides.md has no slides")
        return result

    head = slides[0]
    result.headmatter = dict(head.frontmatter)
    if head.frontmatter_error:
        result.errors.append(f"slide 1 (line {head.start_line}): {head.frontmatter_error}")
    for key in REQUIRED_HEADMATTER:
        if key not in head.frontmatter:
            result.errors.append(f"slide 1 headmatter missing required key: {key}")
    if "fonts" in head.frontmatter:
        result.errors.append(
            "slide 1: do not set `fonts:` — brands/<id>/tokens.css already loads webfonts"
        )
    theme_config = head.frontmatter.get("themeConfig")
    if isinstance(theme_config, dict) and theme_config:
        result.errors.append(
            "slide 1: do not set `themeConfig` colors — use brands/<id>/tokens.css"
        )
    if head.frontmatter.get("colorSchema") not in ("light", "dark"):
        result.warnings.append(
            "slide 1 headmatter: set `colorSchema: light` (or dark); `auto` follows "
            "the viewer's OS and half-switches the theme's element styles"
        )

    theme = str(head.frontmatter.get("theme") or "default")
    layouts = discover_layouts(root, dest, theme)
    if len(layouts) <= 1:
        result.warnings.append(
            "could not load Slidev layouts from node_modules; "
            "run `deck.py new` (or npm install -w) so layout names can be checked"
        )
    lucide = load_lucide_icons(root)
    if not lucide:
        result.warnings.append(
            "could not load @iconify-json/lucide; icon name checks skipped"
        )

    for slide in slides:
        label = f"slide {slide.index} (line {slide.start_line})"
        if slide.frontmatter_error:
            result.errors.append(f"{label}: {slide.frontmatter_error}")
            continue
        layout = slide.frontmatter.get("layout")
        if layout is None and slide.index > 1:
            layout = "default"
        if layout is not None:
            layout_name = str(layout)
            if layouts and layout_name not in layouts:
                result.errors.append(
                    f"{label}: unknown layout {layout_name!r}; "
                    f"known: {', '.join(sorted(layouts))}"
                )

        for match in LUCIDE_TAG_RE.finditer(slide.body):
            tag = match.group(1).lower()
            icon = tag[len("lucide-") :]
            if lucide and icon not in lucide:
                result.errors.append(f"{label}: unknown Lucide icon <{tag} />")

        for finding in _check_tag_balance(slide.body):
            result.errors.append(f"{label}: {finding}")

        if _is_bare_bullet_slide(slide.body):
            result.warnings.append(
                f"{label}: heading + bullets with no icon/mark — add a lucide-* or ok-* mark"
            )
        contract_errors, contract_warnings = check_component_contracts(slide.body)
        result.errors.extend(f"{label}: {finding}" for finding in contract_errors)
        result.warnings.extend(f"{label}: {finding}" for finding in contract_warnings)
        asset_errors, asset_warnings = check_assets(slide, dest)
        result.errors.extend(f"{label}: {finding}" for finding in asset_errors)
        result.warnings.extend(f"{label}: {finding}" for finding in asset_warnings)

    _check_style_imports(dest, result.errors, result.warnings)

    # Client console errors are forwarded into the dev log by Vite, so a
    # running preview's log is the cheapest view of what a browser hit.
    log_path = dest / LOGFILE_NAME
    if log_path.is_file():
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        for line in log_errors(text):
            result.warnings.append(f"dev log: {line}")
    return result


def _render_pass(
    args: argparse.Namespace, root: Path, dest: Path, slug: str, result: AuditResult
) -> None:
    """Render every slide when a preview runs (or --render starts one)."""
    mode = getattr(args, "render", "auto")
    if mode == "off" or not result.visible_slides:
        return
    url = live_preview_url(dest)
    started = False
    if url is None:
        if mode != "on":
            print("  note:  no preview running; `--render` starts one and checks every slide")
            return
        config = _common.load_config(root)
        preferred = int((config.get("preview") or {}).get("presentation_port") or 3030)
        _pid, _port, url, _log = start_preview(
            root, dest, slug, preferred=preferred, timeout=float(args.timeout)
        )
        started = True
    out_dir = dest / Path(getattr(args, "render_dir", None) or RENDER_DIR)
    canvas = canvas_size(result.headmatter)
    try:
        passes = [("light", out_dir, False)]
        if getattr(args, "dark", False):
            passes.append(("dark", out_dir / "dark", True))
        for name, directory, dark in passes:
            print(
                f"  render: {result.visible_slides} slide(s) at {canvas[0]}x{canvas[1]} "
                f"({name}) → {_common.relative_to(directory, root)}/"
            )
            data = render_audit(
                root,
                dest,
                url=url,
                slide_count=result.visible_slides,
                canvas=canvas,
                out_dir=directory,
                dark=dark,
            )
            errors, warnings = render_findings(data)
            result.errors.extend(errors)
            result.warnings.extend(warnings)
        result.rendered = True
    finally:
        if started:
            for note in _common.stop_pidfile(_pidfile(dest)):
                print(f"  {note}")


def cmd_audit(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    slug, dest = _resolve_project(root, args.slug)
    result = audit_deck(root, dest)
    rel = _common.relative_to(dest / "slides.md", root)

    if not result.errors or getattr(args, "render", "auto") == "on":
        _render_pass(args, root, dest, slug, result)

    for message in result.warnings:
        print(f"  warn:  {message}")
    for message in result.errors:
        print(f"  error: {message}")

    checked = "static + render" if result.rendered else "static"
    if result.errors:
        print(
            f"FAIL {rel} — {result.slide_count} slide(s), "
            f"{len(result.errors)} error(s), {len(result.warnings)} warning(s) [{checked}]"
        )
        return 1

    print(
        f"PASS {rel} — {result.slide_count} slide(s), "
        f"{len(result.warnings)} warning(s) [{checked}]"
    )
    return 0


# ── export ───────────────────────────────────────────────────────────────────


def cmd_export(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    slug, dest = _resolve_project(root, args.slug)
    slides = dest / "slides.md"
    if not slides.is_file():
        raise ScaffoldError(f"slides.md missing in {_common.relative_to(dest, root)}")

    config = _common.load_config(root)
    presentation = config.get("presentation") or {}
    export_cfg = presentation.get("export") or {}
    fmt = args.format or str(export_cfg.get("format") or "pdf")
    output_dir = args.output_dir or str(export_cfg.get("output_dir") or "dist")
    out_path = dest / output_dir / f"slides.{fmt}"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        _common.node_bin("npx"),
        "slidev",
        "export",
        "--output",
        str(out_path),
        "--format",
        fmt,
    ]
    if export_cfg.get("with_clicks"):
        command.append("--with-clicks")
    if export_cfg.get("dark"):
        command.append("--dark")

    print(f"Exporting {slug} → {_common.relative_to(out_path, root)}")
    try:
        result = subprocess.run(command, cwd=dest, check=False)
    except FileNotFoundError as exc:
        raise ScaffoldError("npx is not installed or not on PATH") from exc
    if result.returncode != 0:
        raise ScaffoldError(f"slidev export failed with exit {result.returncode}")
    print(f"  wrote: {_common.relative_to(out_path, root)}")
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold, preview, audit, and export a Slidev deck."
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
    new.add_argument(
        "--no-install",
        action="store_true",
        help="skip npm install -w (offline / tests)",
    )
    new.set_defaults(handler=cmd_new)

    dev = sub.add_parser("dev", parents=[common], help="start the Slidev preview")
    dev.add_argument("slug", help="project slug or path under projects/")
    dev.add_argument("--port", type=int, default=None, help="override preview port")
    dev.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="seconds to wait for the preview to become healthy",
    )
    dev.set_defaults(handler=cmd_dev)

    stop = sub.add_parser("stop", parents=[common], help="stop a managed Slidev preview")
    stop.add_argument(
        "slug",
        nargs="?",
        default=None,
        help="project slug (omit to stop every managed deck)",
    )
    stop.set_defaults(handler=cmd_stop)

    audit = sub.add_parser(
        "audit",
        parents=[common],
        help="check slides.md, and render every slide when a preview is running",
    )
    audit.add_argument("slug", help="project slug or path under projects/")
    render_group = audit.add_mutually_exclusive_group()
    render_group.add_argument(
        "--render",
        dest="render",
        action="store_const",
        const="on",
        default="auto",
        help="render every slide, starting a preview if none is running",
    )
    render_group.add_argument(
        "--no-render",
        dest="render",
        action="store_const",
        const="off",
        help="skip the render pass even when a preview is running",
    )
    audit.add_argument(
        "--dark",
        action="store_true",
        help="also render under prefers-color-scheme: dark (into reports/render/dark/)",
    )
    audit.add_argument(
        "--render-dir",
        default=None,
        help=f"directory under the project for the PNGs (default: {RENDER_DIR.as_posix()})",
    )
    audit.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="seconds to wait for a preview started by --render",
    )
    audit.set_defaults(handler=cmd_audit)

    export = sub.add_parser("export", parents=[common], help="export PDF/PPTX/PNG")
    export.add_argument("slug", help="project slug or path under projects/")
    export.add_argument(
        "--format",
        choices=("pdf", "pptx", "png"),
        default=None,
        help="override config.toml [presentation.export] format",
    )
    export.add_argument(
        "--output-dir",
        default=None,
        help="directory under the project (default: dist)",
    )
    export.set_defaults(handler=cmd_export)
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
