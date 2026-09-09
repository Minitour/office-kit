#!/usr/bin/env python3
"""OfficeKit document pipeline — one file per document, no server, no build.

A document is a single self-contained HTML file at ``projects/<slug>/<slug>.html``.
Styles, behaviour, brand tokens, the brand marks, and any embedded image all
live inside it, so it opens straight from disk over ``file://`` and can be
emailed or archived as one attachment. Nothing here starts a preview server,
installs a dependency, or produces a second artifact.

Subcommands
-----------
``new <slug>``      Scaffold from ``.templates/document-html/document.html``:
                    fill the brand region and the header fields, and strip the
                    template's ``officekit:hint`` comments.
``toc <file>``      Regenerate the contents list from the section headings.
``check <file>``    Verify the file is self-contained, branded, accessible, and
                    free of unfilled placeholders. Read-only; exit 1 on failure.
``refresh <file>``  Re-inline the current brand after ``brand.json`` changes, and
                    re-apply the template's shared styles so a fix made to the
                    template reaches documents scaffolded before it.
``embed <file>``    Pull local stylesheets, scripts, and images into the file as
                    inline text or data URIs, in place.

The region between ``/* officekit:brand:start */`` and
``/* officekit:brand:end */`` is script-owned. It is filled from
``brands/<id>/tokens.css`` plus data-URI copies of the marks named in
``brands/<id>/brand.json``, which is how a one-file document carries brand
identity without anyone hand-copying a colour, a font, or a logo path. The
region records the brand id so ``check`` and ``refresh`` stay bound to that
identity. ``check`` fails when the region drifts, so a brand change cannot go
unnoticed.

Remote references are left alone: the webfont ``@import`` in the token sheet is
expected, and a document without a network connection falls back to system
fonts. A reference to a *local* file is an error — that is the one thing that
would stop the file opening on its own.

``new`` renders the HTML template with Jinja. Check and refresh stay
stdlib-only once the file exists.

Usage:
    uv run python scripts/document/doc.py new quarterly-review --title "Quarterly Review"
    uv run python scripts/document/doc.py toc projects/quarterly-review/quarterly-review.html
    uv run python scripts/document/doc.py check projects/quarterly-review/quarterly-review.html
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import importlib.util
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple, Sequence
from urllib.parse import urlsplit

DEFAULT_TEMPLATE = "document-html"
TEMPLATE_FILE = "document.html"

BRAND_START = "/* officekit:brand:start */"
BRAND_END = "/* officekit:brand:end */"
BRAND_ID_RE = re.compile(r"/\*\s*officekit:brand-id:\s*([a-z0-9][a-z0-9-]*)\s*\*/")
STYLES_START = "/* officekit:styles:start */"
STYLES_END = "/* officekit:styles:end */"
SCRIPT_START = "/* officekit:script:start */"
SCRIPT_END = "/* officekit:script:end */"
TOC_START = "<!-- officekit:toc:start -->"
TOC_END = "<!-- officekit:toc:end -->"
CONTENT_MARKER = "<!-- officekit:content -->"

HINT_RE = re.compile(r"[ \t]*<!--\s*officekit:hint\b.*?-->[ \t]*\n?", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"\{\{\s*[A-Za-z_][A-Za-z0-9_]*\s*\}\}")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CSS_URL_RE = re.compile(r"url\(\s*(?P<quote>[\"']?)(?P<url>.*?)(?P=quote)\s*\)", re.DOTALL)
CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\(\s*)?[\"']?(?P<url>[^\"')\s;]+)", re.IGNORECASE)

# A standalone document larger than this is awkward to email; usually an
# oversized embedded image.
SIZE_WARN_BYTES = 2 * 1024 * 1024


class DocError(Exception):
    """Raised when a document cannot be scaffolded, indexed, or read."""


def _load_sibling(name: str, filename: str):
    """Import a module that sits next to this script, by path."""
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - import plumbing
        raise DocError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The packager already knows how to turn a local file into a data URI, resolve
# a workspace root, and inline a whole document. Reuse it rather than keeping a
# second MIME table in step.
_packager = _load_sibling("officekit_document_package", "package.py")


def _load_catalog():
    path = Path(__file__).resolve().parents[1] / "brand" / "catalog.py"
    spec = importlib.util.spec_from_file_location("officekit_brand_catalog", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise DocError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_catalog = _load_catalog()


def _load_common():
    path = Path(__file__).resolve().parents[1] / "common.py"
    spec = importlib.util.spec_from_file_location("officekit_common", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise DocError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_common = _load_common()


# ── Brand region ─────────────────────────────────────────────────────────────


def _logo_sources(logo: object) -> dict[str, str]:
    """Map ``brand.json``'s logo block onto CSS variables, smallest mark first.

    The document header paints a 2rem-tall mark, so the ``small`` entry wins
    when several sizes are declared.
    """
    if isinstance(logo, str) and logo.strip():
        return {"--brand-logo": logo.strip()}
    if not isinstance(logo, dict):
        return {}

    found: dict[str, str] = {}
    for size in ("small", "medium", "large"):
        entry = logo.get(size)
        if not isinstance(entry, dict):
            continue
        # brand.json names the ground a mark is *for*: `light` is the mark used
        # on a light background, which is what a document uses by default.
        for mode, variable in (("light", "--brand-logo"), ("dark", "--brand-logo-on-dark")):
            value = entry.get(mode)
            if isinstance(value, str) and value.strip():
                found.setdefault(variable, value.strip())
    return found


def recorded_brand_id(text: str) -> str | None:
    match = BRAND_ID_RE.search(text)
    return match.group(1) if match else None


def resolve_document_brand(root: Path, explicit: str | None) -> str:
    try:
        return _catalog.resolve_brand_id(root, explicit)
    except _catalog.BrandCatalogError as exc:
        raise DocError(str(exc)) from exc


def _logo_declarations(root: Path, brand_id: str) -> list[str]:
    directory = _catalog.brand_dir(root, brand_id)
    brand_json = directory / "brand.json"
    if not brand_json.is_file():
        return []
    label = f"brands/{brand_id}/brand.json"
    try:
        brand = json.loads(brand_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DocError(f"cannot read {label}: {exc}") from exc

    declarations: list[str] = []
    for variable, relative in _logo_sources(brand.get("logo")).items():
        path = (directory / relative).resolve()
        if not path.is_file():
            raise DocError(f"{label} names a mark that is missing: {relative}")
        uri = _packager.data_uri(path.read_bytes(), _packager.guess_mime(path))
        declarations.append(f'  {variable}: url("{uri}");')
    return declarations


def brand_region(root: Path, brand_id: str | None = None) -> str:
    """Build the script-owned brand block for a standalone document."""
    brand_id = resolve_document_brand(root, brand_id)
    directory = _catalog.brand_dir(root, brand_id)
    tokens = directory / "tokens.css"
    label = f"brands/{brand_id}/tokens.css"
    if not tokens.is_file():
        raise DocError(
            f"{label} is missing; generate the brand first with "
            f"`uv run python scripts/brand/generate.py {brand_id}`"
        )
    try:
        css = tokens.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise DocError(f"cannot read {label}: {exc}") from exc

    blocks = [f"/* officekit:brand-id: {brand_id} */", css]
    declarations = _logo_declarations(root, brand_id)
    if declarations:
        blocks.append(
            "/* Brand marks, embedded so the document carries its own identity. */\n"
            ":root {\n" + "\n".join(declarations) + "\n}"
        )
    return "\n\n".join(blocks)


# ── Marked regions ───────────────────────────────────────────────────────────


def _region_bounds(text: str, start: str, end: str, *, label: str) -> tuple[int, int]:
    first = text.find(start)
    if first < 0:
        raise DocError(f"the {label} start marker is missing: {start}")
    if text.find(start, first + len(start)) >= 0:
        raise DocError(f"the {label} start marker appears more than once")
    last = text.find(end, first + len(start))
    if last < 0:
        raise DocError(f"the {label} end marker is missing: {end}")
    return first + len(start), last


def _region_body(text: str, start: str, end: str, *, label: str) -> str:
    opening, closing = _region_bounds(text, start, end, label=label)
    return text[opening:closing]


def _marker_indent(text: str, marker: str) -> str:
    index = text.find(marker)
    if index < 0:
        return ""
    line_start = text.rfind("\n", 0, index) + 1
    indent = text[line_start:index]
    return indent if not indent.strip() else ""


def _indent_block(body: str, indent: str) -> str:
    return "\n".join(
        indent + line if line.strip() else line for line in body.split("\n")
    )


def _replace_region(text: str, start: str, end: str, body: str, *, label: str) -> str:
    opening, closing = _region_bounds(text, start, end, label=label)
    indent = _marker_indent(text, start)
    block = "\n" + _indent_block(body, indent) + "\n" + indent
    return text[:opening] + block + text[closing:]


def _replace_span(text: str, start: str, end: str, body: str, *, label: str) -> str:
    """Swap the text between two markers verbatim, indentation included."""
    opening, closing = _region_bounds(text, start, end, label=label)
    return text[:opening] + body + text[closing:]


class Shell(NamedTuple):
    """A template-owned span of a document, and the template's copy of it."""

    label: str
    start: str
    end: str
    body: str


def template_text(root: Path, template: str = DEFAULT_TEMPLATE) -> str:
    path = root / ".templates" / template / TEMPLATE_FILE
    if not path.is_file():
        raise DocError(f"template is missing: {_relative(path, root)}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocError(f"cannot read {path}: {exc}") from exc
    # Documents are scaffolded with hints stripped; compare like with like.
    return HINT_RE.sub("", text)


def shell_spans(root: Path, template: str = DEFAULT_TEMPLATE) -> list[Shell]:
    """The template-owned blocks of a document, read back out of the template.

    A self-contained file cannot pick up a template fix on its own: every rule
    it needs was copied into it at scaffold time. Naming the spans the template
    owns — the shell CSS between the brand and project style regions, and the
    progressive-enhancement script — is what lets ``refresh`` carry a later fix
    into documents that already exist. Everything outside them, content and the
    ``officekit:styles`` region, belongs to the document and is never touched.
    """
    text = template_text(root, template)
    return [
        Shell(label, start, end, _region_body(text, start, end, label=label))
        for label, start, end in (
            ("shared styles", BRAND_END, STYLES_START),
            ("shared script", SCRIPT_START, SCRIPT_END),
        )
    ]


def _normalize(text: str) -> str:
    """Collapse whitespace so indentation differences never read as drift."""
    return " ".join(text.split())


# ── Document parsing ─────────────────────────────────────────────────────────


HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})


class _DocumentParser(HTMLParser):
    """Collect exactly what the checks and the contents list need."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang: str | None = None
        self.title: str | None = None
        self.description: str | None = None
        self.ids: list[str] = []
        self.fragments: list[str] = []
        self.images: list[dict[str, str | None]] = []
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.headings: list[tuple[int, str]] = []
        self.sections: list[tuple[str | None, str]] = []
        self.css: list[str] = []
        self.has_toc = False
        self.tables = 0
        self.captions = 0

        self._capture: list[str] | None = None
        self._capture_tag: str | None = None
        self._heading_level = 0
        self._section_stack: list[list] = []
        self._in_style = False

    # -- helpers ----------------------------------------------------------

    def _start_capture(self, tag: str) -> None:
        self._capture = []
        self._capture_tag = tag

    def _finish_capture(self) -> str:
        text = " ".join("".join(self._capture or []).split())
        self._capture = None
        self._capture_tag = None
        return text

    # -- parser hooks -----------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        collected = dict(attrs)
        identifier = collected.get("id")
        if identifier:
            self.ids.append(identifier)

        if tag == "html":
            self.lang = collected.get("lang")
        elif tag == "title":
            self._start_capture(tag)
        elif tag == "meta":
            if (collected.get("name") or "").lower() == "description":
                self.description = collected.get("content")
        elif tag in HEADING_TAGS:
            self._heading_level = int(tag[1])
            self._start_capture(tag)
        elif tag == "section":
            self._section_stack.append([identifier, None])
        elif tag == "a":
            href = (collected.get("href") or "").strip()
            if href.startswith("#") and len(href) > 1:
                self.fragments.append(href[1:])
        elif tag == "img":
            self.images.append(collected)
        elif tag == "link":
            rel = (collected.get("rel") or "").lower().split()
            if "stylesheet" in rel:
                self.stylesheets.append(collected.get("href") or "")
        elif tag == "script":
            source = collected.get("src")
            if source:
                self.scripts.append(source)
        elif tag == "style":
            self._in_style = True
        elif tag == "nav":
            if "doc-toc" in (collected.get("class") or "").split():
                self.has_toc = True
        elif tag == "table":
            self.tables += 1
        elif tag == "caption":
            self.captions += 1

    def handle_endtag(self, tag: str) -> None:
        if self._capture is not None and tag == self._capture_tag:
            text = self._finish_capture()
            if tag == "title":
                self.title = text
            else:
                self.headings.append((self._heading_level, text))
                # A section is labelled by its own first h2.
                if self._heading_level == 2 and self._section_stack:
                    current = self._section_stack[-1]
                    if current[1] is None:
                        current[1] = text
        elif tag == "section" and self._section_stack:
            identifier, label = self._section_stack.pop()
            # Only top-level sections belong in the contents list.
            if not self._section_stack:
                self.sections.append((identifier, label or ""))
        elif tag == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self.css.append(data)
        if self._capture is not None:
            self._capture.append(data)


def parse_document(text: str) -> _DocumentParser:
    parser = _DocumentParser()
    try:
        parser.feed(text)
        parser.close()
    except AssertionError as exc:  # malformed markup surfaces as an assertion
        raise DocError(f"cannot parse the document: {exc}") from exc
    return parser


# ── Contents list ────────────────────────────────────────────────────────────


def render_toc(sections: Sequence[tuple[str | None, str]]) -> str:
    """Render the contents list. `_replace_region` adds the marker's indent."""
    entries = [(anchor, label) for anchor, label in sections if anchor and label]
    if not entries:
        return "<ul></ul>"
    lines = ["<ul>"]
    for anchor, label in entries:
        lines.append(
            f'  <li><a href="#{html.escape(anchor, quote=True)}">'
            f"{html.escape(label)}</a></li>"
        )
    lines.append("</ul>")
    return "\n".join(lines)


def rebuild_toc(text: str) -> tuple[str, int]:
    """Rewrite the contents region from the section headings."""
    parser = parse_document(text)
    updated = _replace_region(
        text, TOC_START, TOC_END, render_toc(parser.sections), label="contents"
    )
    listed = sum(1 for anchor, label in parser.sections if anchor and label)
    return updated, listed


# ── Checks ───────────────────────────────────────────────────────────────────


def _classify(url: str | None) -> str:
    value = (url or "").strip()
    if not value:
        return "empty"
    try:
        parts = urlsplit(value)
    except ValueError:
        return "unusable"
    if parts.scheme == "data":
        return "data"
    if parts.scheme or parts.netloc or value.startswith("//"):
        return "remote"
    if not parts.path:
        return "fragment"
    return "local"


def check_document(path: Path, root: Path) -> tuple[list[str], list[str], dict[str, int]]:
    """Return (errors, warnings, stats) for one standalone document."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocError(f"cannot read {path}: {exc}") from exc

    errors: list[str] = []
    warnings: list[str] = []
    parser = parse_document(text)

    # -- leftovers from the template ---------------------------------------
    for placeholder in sorted(set(PLACEHOLDER_RE.findall(text))):
        errors.append(f"unfilled placeholder {placeholder}")
    if CONTENT_MARKER in text:
        errors.append(
            "the officekit:content marker is still in <main>: no content was written"
        )
    if "officekit:hint" in text:
        errors.append(
            "template officekit:hint comments are still present; scaffold with `doc.py new`"
        )
    if re.search(r"[Ll]orem ipsum", text):
        errors.append("placeholder copy: 'lorem ipsum'")
    for marker in re.findall(r"\b(TODO|FIXME)\b", text):
        errors.append(f"unfinished marker in the document text: {marker}")

    # -- brand region -------------------------------------------------------
    try:
        current = _region_body(text, BRAND_START, BRAND_END, label="brand region")
    except DocError as exc:
        errors.append(str(exc))
    else:
        if not current.strip():
            errors.append("the brand region is empty; run `doc.py refresh <file>`")
        else:
            brand_id = recorded_brand_id(text) or recorded_brand_id(current)
            try:
                expected = brand_region(root, brand_id)
            except DocError as exc:
                errors.append(str(exc))
            else:
                if _normalize(current) != _normalize(expected):
                    label = brand_id or "the default brand"
                    errors.append(
                        f"the brand region no longer matches {label}; "
                        "run `doc.py refresh <file>`"
                    )

    # -- template-owned blocks ----------------------------------------------
    # Advisory, not fatal: an older shell still renders correctly, it just
    # misses fixes made to the template since this document was scaffolded.
    try:
        spans = shell_spans(root)
    except DocError:
        spans = []
    for span in spans:
        if span.start not in text or span.end not in text:
            continue
        try:
            current_shell = _region_body(text, span.start, span.end, label=span.label)
        except DocError:
            continue
        if _normalize(current_shell) != _normalize(span.body):
            warnings.append(
                f"the {span.label} block is older than the document template; "
                "run `doc.py refresh <file>` to pick up template fixes"
            )

    # -- self-containment ---------------------------------------------------
    references = (
        [("stylesheet", url) for url in parser.stylesheets]
        + [("script", url) for url in parser.scripts]
        + [("image", (attrs.get("src") or "")) for attrs in parser.images]
    )
    for kind, url in references:
        classification = _classify(url)
        if classification == "local":
            errors.append(
                f"{kind} points at a local file ({url}); a standalone document must "
                "carry it inline — run `doc.py embed <file>`"
            )
        elif classification == "remote":
            warnings.append(f"{kind} needs the network when the file is opened: {url}")
        elif classification == "unusable":
            errors.append(f"{kind} has an unusable URL: {url}")

    css = "".join(parser.css)
    for match in CSS_URL_RE.finditer(css):
        url = match.group("url").strip()
        if _classify(url) == "local":
            errors.append(
                f"the stylesheet points at a local file ({url}); run `doc.py embed <file>`"
            )
    for match in CSS_IMPORT_RE.finditer(css):
        if _classify(match.group("url")) == "local":
            errors.append(
                f"the stylesheet imports a local file ({match.group('url')}); "
                "run `doc.py embed <file>`"
            )

    # -- structure and accessibility ---------------------------------------
    if not (parser.lang or "").strip():
        errors.append("<html> has no lang attribute")
    if not (parser.title or "").strip():
        errors.append("<title> is empty or missing")

    top_level = [text_ for level, text_ in parser.headings if level == 1]
    if len(top_level) != 1:
        errors.append(f"expected exactly one <h1>, found {len(top_level)}")

    previous = 0
    for level, heading in parser.headings:
        if previous and level > previous + 1:
            errors.append(
                f"heading level jumps from h{previous} to h{level} at {heading!r}"
            )
        previous = level

    for attrs in parser.images:
        if "alt" in attrs:
            continue
        hidden = (attrs.get("aria-hidden") or "").lower() == "true"
        presentational = (attrs.get("role") or "").lower() in ("presentation", "none")
        if not (hidden or presentational):
            errors.append(
                f"<img> has no alt attribute: {attrs.get('src', '')[:60] or '(no src)'}"
            )

    known = set(parser.ids)
    for fragment in sorted(set(parser.fragments)):
        if fragment not in known:
            errors.append(f"in-page link #{fragment} has no matching id")

    for index, (anchor, label) in enumerate(parser.sections, start=1):
        if not anchor:
            errors.append(f"section {index} has no id, so nothing can link to it")
        if not label:
            errors.append(
                f"section {anchor or index} has no <h2>, so it cannot be listed"
            )

    # -- contents list ------------------------------------------------------
    if TOC_START in text:
        try:
            listed = _region_body(text, TOC_START, TOC_END, label="contents")
        except DocError as exc:
            errors.append(str(exc))
        else:
            if _normalize(listed) != _normalize(render_toc(parser.sections)):
                errors.append(
                    "the contents list does not match the sections; run `doc.py toc <file>`"
                )
    elif parser.has_toc:
        errors.append(
            "the contents panel has no officekit:toc markers, so it cannot be verified"
        )

    if parser.has_toc and "scroll-padding-top" not in css:
        errors.append(
            "the stylesheet sets no scroll-padding-top, so a contents link "
            "leaves its heading flush against the top of the viewport"
        )

    # -- advisory -----------------------------------------------------------
    if not (parser.description or "").strip():
        warnings.append("<meta name=\"description\"> is empty or missing")
    if parser.tables and parser.captions < parser.tables:
        warnings.append(
            f"{parser.tables - parser.captions} of {parser.tables} table(s) have no <caption>"
        )
    size = len(text.encode("utf-8"))
    if size > SIZE_WARN_BYTES:
        warnings.append(
            f"the file is {size / 1024 / 1024:.1f} MB, which is large to email; "
            "consider smaller embedded images"
        )

    stats = {
        "sections": len(parser.sections),
        "headings": len(parser.headings),
        "images": len(parser.images),
        "bytes": size,
    }
    return errors, warnings, stats


# ── File helpers ─────────────────────────────────────────────────────────────


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        raise DocError(f"cannot write {path}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _workspace_root(explicit: Path | None, start: Path) -> Path:
    if explicit is not None:
        root = explicit.expanduser().resolve()
        if not _catalog.is_workspace_root(root):
            raise DocError(f"{root} is not an OfficeKit workspace")
        return root
    try:
        return _packager.find_workspace_root(start)
    except _packager.PackageError as exc:
        raise DocError(str(exc)) from exc


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


# ── Commands ─────────────────────────────────────────────────────────────────


def _brand_name(root: Path, brand_id: str | None = None) -> str:
    try:
        brand_id = resolve_document_brand(root, brand_id)
    except DocError:
        return "OfficeKit"
    brand_json = _catalog.brand_dir(root, brand_id) / "brand.json"
    if not brand_json.is_file():
        return "OfficeKit"
    try:
        brand = json.loads(brand_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "OfficeKit"
    name = ((brand.get("meta") or {}).get("name") or "").strip()
    return name or "OfficeKit"


def cmd_new(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace_root, Path.cwd())
    slug = args.slug.strip()
    if not SLUG_RE.match(slug):
        raise DocError(
            f"{slug!r} is not a usable slug; use lowercase letters, digits, and hyphens"
        )

    template = root / ".templates" / args.template / TEMPLATE_FILE
    if not template.is_file():
        raise DocError(f"template is missing: {_relative(template, root)}")

    target = root / "projects" / slug / f"{slug}.html"
    if target.exists() and not args.force:
        raise DocError(
            f"{_relative(target, root)} already exists; edit it, or pass --force to replace it"
        )

    try:
        text = template.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocError(f"cannot read {template}: {exc}") from exc

    if args.date:
        try:
            date = dt.date.fromisoformat(args.date)
        except ValueError as exc:
            raise DocError(f"--date must be an ISO date such as 2026-09-07: {exc}") from exc
    else:
        date = dt.date.today()

    brand_id = resolve_document_brand(root, getattr(args, "brand", None))
    title = args.title or slug.replace("-", " ").title()
    text = HINT_RE.sub("", text)
    try:
        text = _common.render_string(
            text,
            {
                "title": title,
                "subtitle": args.subtitle or None,
                "author": args.author or _brand_name(root, brand_id),
                "date_iso": date.isoformat(),
                "date_human": f"{date.day} {date:%B %Y}",
                "description": args.description or args.subtitle or title,
                "footer": args.footer or None,
            },
            autoescape=True,
        )
    except _common.ScaffoldError as exc:
        raise DocError(str(exc)) from exc
    text = _replace_region(
        text, BRAND_START, BRAND_END, brand_region(root, brand_id), label="brand region"
    )

    leftover = sorted(set(PLACEHOLDER_RE.findall(text)))
    if leftover:
        raise DocError(
            "the template carries placeholders this command does not fill: "
            + ", ".join(leftover)
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target, text)

    print(f"Created {_relative(target, root)} ({len(text.encode('utf-8'))} bytes)")
    print(f"  open:  {target.as_uri()}")
    print(
        "  next:  replace the officekit:content marker with the sections, then run "
        "`doc.py toc` and `doc.py check`"
    )
    return 0


def cmd_toc(args: argparse.Namespace) -> int:
    path = args.document.expanduser().resolve()
    root = _workspace_root(args.workspace_root, path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocError(f"cannot read {path}: {exc}") from exc

    if TOC_START not in text:
        print(f"{_relative(path, root)} has no contents panel; nothing to do")
        return 0

    updated, listed = rebuild_toc(text)
    if updated == text:
        print(f"{_relative(path, root)} contents already lists {listed} section(s)")
        return 0
    _atomic_write(path, updated)
    print(f"Rebuilt the contents of {_relative(path, root)}: {listed} section(s)")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    path = args.document.expanduser().resolve()
    if not path.is_file():
        raise DocError(f"document does not exist: {path}")
    root = _workspace_root(args.workspace_root, path)
    errors, warnings, stats = check_document(path, root)

    label = _relative(path, root)
    for message in warnings:
        print(f"  warn:  {message}")
    for message in errors:
        print(f"  error: {message}")

    summary = (
        f"{stats['sections']} section(s), {stats['images']} image(s), "
        f"{stats['bytes'] / 1024:.0f} KB"
    )
    if errors:
        print(f"FAIL {label} — {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASS {label} — self-contained, {summary}")
    print(f"  open:  {path.as_uri()}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    documents = [path.expanduser().resolve() for path in args.documents]
    if args.all:
        root = _workspace_root(args.workspace_root, Path.cwd())
        documents.extend(
            sorted(
                candidate
                for candidate in (root / "projects").glob("*/*.html")
                if BRAND_START in candidate.read_text(encoding="utf-8", errors="ignore")
            )
        )
    if not documents:
        raise DocError("name at least one document, or pass --all")

    root = _workspace_root(args.workspace_root, documents[0])
    try:
        spans = shell_spans(root)
    except DocError as exc:
        spans = []
        print(f"  warn:  {exc}; refreshing the brand only")

    changed = 0
    for path in documents:
        if not path.is_file():
            raise DocError(f"document does not exist: {path}")
        label = _relative(path, root)
        text = path.read_text(encoding="utf-8")
        region = brand_region(root, recorded_brand_id(text))

        updated = _replace_region(text, BRAND_START, BRAND_END, region, label="brand region")
        moved = ["brand"] if updated != text else []

        for span in spans:
            if span.start not in updated or span.end not in updated:
                # A hand-migrated document without the markers: its own code and
                # the template's are indistinguishable, so leave the block alone.
                print(f"  warn:  {label} has no {span.label} markers; that block was left alone")
                continue
            reshelled = _replace_span(
                updated, span.start, span.end, span.body, label=span.label
            )
            if reshelled != updated:
                moved.append(span.label)
            updated = reshelled

        if not moved:
            print(f"{label} already current")
            continue
        _atomic_write(path, updated)
        changed += 1
        print(f"Refreshed the {' and '.join(moved)} in {label}")
    if changed:
        print(f"{changed} document(s) updated; re-run `doc.py check` on each")
    return 0


def cmd_embed(args: argparse.Namespace) -> int:
    path = args.document.expanduser().resolve()
    if not path.is_file():
        raise DocError(f"document does not exist: {path}")
    root = _workspace_root(args.workspace_root, path)
    try:
        result = _packager.package_document(path, workspace_root=root)
    except _packager.PackageError as exc:
        raise DocError(str(exc)) from exc

    original = path.read_text(encoding="utf-8")
    if result.html == original:
        print(f"{_relative(path, root)} already carries every local file inline")
        return 0
    _atomic_write(path, result.html)
    inlined = max(len(result.sources) - 1, 0)
    print(f"Inlined {inlined} local file(s) into {_relative(path, root)}")
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scaffold, brand, index, and verify a self-contained OfficeKit HTML "
            "document. One file, opened straight from disk."
        )
    )
    root_help = "workspace root (default: nearest parent holding config.toml or brands/)"
    parser.add_argument("--workspace-root", type=Path, default=None, help=root_help)

    # Repeated on every subcommand so the flag works on either side of it.
    # SUPPRESS keeps an absent subcommand copy from clobbering the value the
    # top-level parser already stored.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--workspace-root", type=Path, default=argparse.SUPPRESS, help=root_help
    )

    subcommands = parser.add_subparsers(dest="command", required=True)

    new = subcommands.add_parser(
        "new", parents=[common], help="scaffold projects/<slug>/<slug>.html"
    )
    new.add_argument("slug", help="project slug: lowercase letters, digits, hyphens")
    new.add_argument("--title", default=None, help="document title (default: the slug)")
    new.add_argument("--subtitle", default=None, help="optional subtitle")
    new.add_argument("--author", default=None, help="byline (default: the brand name)")
    new.add_argument("--date", default=None, help="ISO date (default: today)")
    new.add_argument("--description", default=None, help="meta description")
    new.add_argument("--footer", default=None, help="footer line (omitted when absent)")
    new.add_argument("--template", default=DEFAULT_TEMPLATE, help="directory under .templates/")
    new.add_argument("--force", action="store_true", help="replace an existing document")
    new.add_argument(
        "--brand",
        default=None,
        help="brand id under brands/ (default: config.toml [brand] default)",
    )
    new.set_defaults(handler=cmd_new)

    toc = subcommands.add_parser(
        "toc", parents=[common], help="rebuild the contents list from the sections"
    )
    toc.add_argument("document", type=Path)
    toc.set_defaults(handler=cmd_toc)

    check = subcommands.add_parser(
        "check", parents=[common], help="verify a document; exit 1 on failure"
    )
    check.add_argument("document", type=Path)
    check.set_defaults(handler=cmd_check)

    refresh = subcommands.add_parser(
        "refresh", parents=[common], help="re-inline the current brand"
    )
    refresh.add_argument("documents", type=Path, nargs="*")
    refresh.add_argument("--all", action="store_true", help="every document under projects/")
    refresh.set_defaults(handler=cmd_refresh)

    embed = subcommands.add_parser(
        "embed", parents=[common], help="inline local files, in place"
    )
    embed.add_argument("document", type=Path)
    embed.set_defaults(handler=cmd_embed)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (DocError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
