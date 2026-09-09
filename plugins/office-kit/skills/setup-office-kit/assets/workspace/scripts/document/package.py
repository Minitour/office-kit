#!/usr/bin/env python3
"""Package a standalone OfficeKit HTML document into one self-contained file.

Reads a document entry file (normally ``projects/<slug>/index.html``) and writes
a single HTML artifact that carries every local dependency inside it:

  ``<link rel="stylesheet">``   the stylesheet text, as a ``<style>`` element
  ``<script src="...">``        the script text, as an inline ``<script>``
  ``<img src="...">``           ``src`` rewritten to a base64 data URI
  CSS ``url(...)``              fonts, images, and masks as data URIs
  CSS ``@import``               the imported stylesheet text, spliced in place

Remote references are left exactly as written: anything carrying a URL scheme
(``https:``, ``data:``, ``mailto:``), a protocol-relative ``//host/path`` URL, or
a bare fragment (``#section``, ``url(#gradient)``) passes through untouched, so
the webfont sheet in ``brands/<id>/tokens.css`` and outbound links keep working.

Every local reference resolves against the file that names it — HTML paths
against the HTML file, CSS paths against that stylesheet — which is what lets
the shared ``../../brands/<id>/tokens.css`` sheet and its own relative asset
paths both land correctly. Referenced files must sit inside the workspace root,
found by walking up from the entry file to the directory holding
``config.toml`` or ``brands/*/brand.json``. Missing files, references that
escape the workspace, and an output path that collides with a source file are
all hard errors. Sources are only ever read.

Two deliberate limits. ``defer`` and ``async`` are dropped when a script is
inlined, because an inline script runs where it sits; the OfficeKit template
loads its script at the end of ``<body>``, where the behaviour is the same.
And these are left verbatim, so a local one stays broken in the packaged file:
``srcset``, ``style="..."`` attributes, ``<link>`` relations other than
``stylesheet``, ``<iframe>``, ``<video>``/``<audio>`` sources, and ``poster``.

Stdlib only.

Usage:
    python scripts/document/package.py projects/<slug>/index.html \
        projects/<slug>/dist/<slug>.html
"""

from __future__ import annotations

import argparse
import base64
import html
import importlib.util
import mimetypes
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import unquote, urlsplit

MAX_CSS_DEPTH = 16


def _load_catalog():
    path = Path(__file__).resolve().parents[1] / "brand" / "catalog.py"
    spec = importlib.util.spec_from_file_location("officekit_brand_catalog", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_catalog = _load_catalog()

# Types the stdlib guesses inconsistently across platforms, or not at all.
MIME_BY_SUFFIX = {
    ".avif": "image/avif",
    ".css": "text/css",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".js": "text/javascript",
    ".otf": "font/otf",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ttf": "font/ttf",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

_CSS_IMPORT_RE = re.compile(
    r"@import\s+"
    r"(?P<target>url\(\s*(?:\"[^\"]*\"|'[^']*'|[^)\s]*)\s*\)|\"[^\"]*\"|'[^']*')"
    r"(?P<condition>[^;]*);",
    re.IGNORECASE,
)
_CSS_URL_RE = re.compile(
    r"url\(\s*(?P<quote>[\"']?)(?P<url>.*?)(?P=quote)\s*\)",
    re.DOTALL,
)
# The negative lookbehind keeps this off `data-src=` while `src\s*=` keeps it
# off `srcset=`.
_SRC_ATTR_RE = re.compile(
    r"""(?<![-\w])src\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""",
    re.IGNORECASE,
)
_CLOSE_SCRIPT_RE = re.compile(r"</(?=script)", re.IGNORECASE)
_CLOSE_STYLE_RE = re.compile(r"</(?=style)", re.IGNORECASE)


class PackageError(Exception):
    """Raised when a document cannot be packaged into a single file."""


@dataclass(frozen=True)
class PackageResult:
    """Packaged markup plus the local files that went into it."""

    html: str
    workspace_root: Path
    sources: tuple[Path, ...]


def find_workspace_root(start: Path) -> Path:
    """Walk up from `start` to the directory holding config.toml or brands/."""
    try:
        return _catalog.find_workspace_root(start)
    except _catalog.BrandCatalogError as exc:
        raise PackageError(str(exc)) from exc


def is_workspace_root(path: Path) -> bool:
    return _catalog.is_workspace_root(path)


def guess_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in MIME_BY_SUFFIX:
        return MIME_BY_SUFFIX[suffix]
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def data_uri(payload: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PackageError(f"cannot read {label} {path}: {exc}") from exc


def _read_text(path: Path, label: str) -> str:
    try:
        return _read_bytes(path, label).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackageError(f"{label} is not valid UTF-8: {path}") from exc


def _unwrap_css_target(target: str) -> str:
    """Strip the `url(...)` wrapper and quotes off an @import target."""
    value = target.strip()
    if value[:4].lower() == "url(" and value.endswith(")"):
        value = value[4:-1].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.strip()


def _escape_script_text(code: str) -> str:
    """Break `</script` so inlined code cannot close its own element."""
    return _CLOSE_SCRIPT_RE.sub(r"<\\/", code)


def _escape_style_text(css: str) -> str:
    """Break `</style` so inlined CSS cannot close its own element."""
    return _CLOSE_STYLE_RE.sub(r"<\\/", css)


def _attr_dict(attrs: Iterable[tuple[str, str | None]]) -> dict[str, str | None]:
    collected: dict[str, str | None] = {}
    for name, value in attrs:
        collected.setdefault(name, value)  # HTML keeps the first duplicate
    return collected


def _quoted_attr(name: str, value: str | None) -> str:
    if not value:
        return ""
    return f' {name}="{html.escape(value, quote=True)}"'


@dataclass(frozen=True)
class _Element:
    """A candidate element, located by character offsets into the source."""

    tag: str
    attrs: dict[str, str | None]
    start: int  # index of the opening "<"
    end: int  # index just past the element
    content_start: int  # inner-text span; empty span when there is no content
    content_end: int


class _HtmlScanner(HTMLParser):
    """Locate rewritable elements without disturbing the rest of the markup.

    Offsets are kept so the packager can splice replacements into the original
    text; anything it does not touch survives byte for byte.
    """

    TARGETS = ("img", "link", "script", "style")

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.elements: list[_Element] = []
        self._line_starts = [0] + [
            index + 1 for index, char in enumerate(source) if char == "\n"
        ]
        self._open: tuple[str, dict[str, str | None], int, int] | None = None

    def _position(self) -> int:
        line, offset = self.getpos()
        return self._line_starts[line - 1] + offset

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        start = self._position()
        end = start + len(self.get_starttag_text() or "")
        if tag in ("script", "style"):
            # Both are CDATA elements: wait for the end tag to bound the content.
            self._open = (tag, _attr_dict(attrs), start, end)
        elif tag in ("img", "link"):
            self.elements.append(_Element(tag, _attr_dict(attrs), start, end, end, end))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # `<img />` and friends never reach handle_starttag.
        if tag in self.TARGETS:
            start = self._position()
            end = start + len(self.get_starttag_text() or "")
            self.elements.append(_Element(tag, _attr_dict(attrs), start, end, end, end))

    def handle_endtag(self, tag: str) -> None:
        if self._open is None or tag != self._open[0]:
            return
        open_tag, attrs, start, content_start = self._open
        content_end = self._position()
        closing = self.source.find(">", content_end)
        end = len(self.source) if closing < 0 else closing + 1
        self.elements.append(
            _Element(open_tag, attrs, start, end, content_start, content_end)
        )
        self._open = None

    def scan(self) -> list[_Element]:
        try:
            self.feed(self.source)
            self.close()
        except AssertionError as exc:  # malformed markup surfaces as an assertion
            raise PackageError(f"cannot parse the document: {exc}") from exc
        if self._open is not None:
            raise PackageError(
                f"<{self._open[0]}> is never closed; fix the markup before packaging"
            )
        return self.elements


class _Packager:
    """Inlines one document, recording every local file it reads."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.sources: list[Path] = []

    # -- helpers ----------------------------------------------------------

    def _record(self, path: Path) -> None:
        if path not in self.sources:
            self.sources.append(path)

    def _label(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def resolve(self, url: str | None, *, base_dir: Path, label: str) -> Path | None:
        """Resolve a local URL against the referring file; None when remote."""
        if url is None or not url.strip():
            return None
        url = url.strip()
        try:
            parts = urlsplit(url)
        except ValueError as exc:
            raise PackageError(f"{label} has an unusable URL {url!r}: {exc}") from exc
        # A scheme, a host, or a path-less fragment means somebody else owns it.
        if parts.scheme or parts.netloc or not parts.path:
            return None

        target = unquote(parts.path)
        if target.startswith("/"):
            raise PackageError(
                f"{label} uses the root-relative path {url!r}; packaging needs a "
                "path relative to the referring file"
            )

        path = (base_dir / target).resolve()
        if not _within(path, self.root):
            raise PackageError(
                f"{label} points outside the workspace root {self.root}: {url!r} "
                f"resolves to {path}"
            )
        if not path.exists():
            raise PackageError(
                f"{label} references a missing file: {url!r} (expected at {path})"
            )
        if not path.is_file():
            raise PackageError(
                f"{label} does not reference a regular file: {url!r} ({path})"
            )
        return path

    # -- CSS --------------------------------------------------------------

    def load_css(self, path: Path, *, stack: tuple[Path, ...]) -> str:
        if path in stack:
            chain = " -> ".join(self._label(item) for item in (*stack, path))
            raise PackageError(f"stylesheet import cycle: {chain}")
        if len(stack) >= MAX_CSS_DEPTH:
            raise PackageError(
                f"stylesheet imports nest deeper than {MAX_CSS_DEPTH} levels: "
                f"{self._label(path)}"
            )
        self._record(path)
        return self.inline_css(
            _read_text(path, "stylesheet"),
            base_dir=path.parent,
            origin=self._label(path),
            stack=(*stack, path),
        )

    def inline_css(
        self,
        css: str,
        *,
        base_dir: Path,
        origin: str,
        stack: tuple[Path, ...] = (),
    ) -> str:
        css = self._inline_imports(css, base_dir=base_dir, origin=origin, stack=stack)
        return self._inline_urls(css, base_dir=base_dir, origin=origin, stack=stack)

    def _inline_imports(
        self, css: str, *, base_dir: Path, origin: str, stack: tuple[Path, ...]
    ) -> str:
        label = f"@import in {origin}"

        def replace(match: re.Match[str]) -> str:
            url = _unwrap_css_target(match.group("target"))
            path = self.resolve(url, base_dir=base_dir, label=label)
            if path is None:
                return match.group(0)
            condition = match.group("condition").strip()
            if condition.lower().startswith(("layer", "supports")):
                raise PackageError(
                    f"{label} carries {condition!r}, which cannot survive inlining; "
                    f"drop the condition or merge {url!r} by hand"
                )
            text = self.load_css(path, stack=stack)
            if not condition:
                return text
            # A media condition is equivalent to wrapping the imported rules.
            return f"@media {condition} {{\n{text}\n}}"

        return _CSS_IMPORT_RE.sub(replace, css)

    def _inline_urls(
        self, css: str, *, base_dir: Path, origin: str, stack: tuple[Path, ...]
    ) -> str:
        label = f"url() in {origin}"

        def replace(match: re.Match[str]) -> str:
            url = match.group("url").strip()
            path = self.resolve(url, base_dir=base_dir, label=label)
            if path is None:
                return match.group(0)
            if path.suffix.lower() == ".css":
                # Nested sheet: inline it first so its own relative paths are
                # already data URIs by the time it becomes opaque.
                payload = self.load_css(path, stack=stack).encode("utf-8")
                return f'url("{data_uri(payload, "text/css")}")'
            self._record(path)
            payload = _read_bytes(path, label)
            return f'url("{data_uri(payload, guess_mime(path))}")'

        return _CSS_URL_RE.sub(replace, css)

    # -- HTML -------------------------------------------------------------

    def package(self, entry: Path) -> str:
        self._record(entry)
        source = _read_text(entry, "document")
        origin = self._label(entry)
        base_dir = entry.parent

        edits: list[tuple[int, int, str]] = []
        for element in _HtmlScanner(source).scan():
            original = source[element.start : element.end]
            content = source[element.content_start : element.content_end]
            edit = self._rewrite(
                element, original, content, base_dir=base_dir, origin=origin
            )
            if edit is None:
                continue
            start, end, replacement = edit
            if replacement != source[start:end]:
                edits.append(edit)
        return _splice(source, edits)

    def _rewrite(
        self,
        element: _Element,
        original: str,
        content: str,
        *,
        base_dir: Path,
        origin: str,
    ) -> tuple[int, int, str] | None:
        if element.tag == "link":
            return self._rewrite_link(element, base_dir=base_dir, origin=origin)
        if element.tag == "script":
            return self._rewrite_script(
                element, content, base_dir=base_dir, origin=origin
            )
        if element.tag == "img":
            return self._rewrite_img(
                element, original, base_dir=base_dir, origin=origin
            )
        if element.tag == "style":
            return self._rewrite_style(
                element, content, base_dir=base_dir, origin=origin
            )
        return None

    def _rewrite_link(
        self, element: _Element, *, base_dir: Path, origin: str
    ) -> tuple[int, int, str] | None:
        rel = (element.attrs.get("rel") or "").lower().split()
        if "stylesheet" not in rel:
            return None
        label = f'<link rel="stylesheet"> in {origin}'
        path = self.resolve(element.attrs.get("href"), base_dir=base_dir, label=label)
        if path is None:
            return None
        css = _escape_style_text(self.load_css(path, stack=()).strip())
        carried = _quoted_attr("media", element.attrs.get("media")) + _quoted_attr(
            "title", element.attrs.get("title")
        )
        return (element.start, element.end, f"<style{carried}>\n{css}\n</style>")

    def _rewrite_script(
        self, element: _Element, content: str, *, base_dir: Path, origin: str
    ) -> tuple[int, int, str] | None:
        src = element.attrs.get("src")
        label = f"<script> in {origin}"
        path = self.resolve(src, base_dir=base_dir, label=label)
        if path is None:
            return None
        if content.strip():
            raise PackageError(
                f"{label} has both src={src!r} and inline code; browsers ignore the "
                "inline code, so remove one of them"
            )
        self._record(path)
        code = _escape_script_text(_read_text(path, "script").strip())
        carried = _quoted_attr("type", element.attrs.get("type"))
        return (element.start, element.end, f"<script{carried}>\n{code}\n</script>")

    def _rewrite_img(
        self, element: _Element, original: str, *, base_dir: Path, origin: str
    ) -> tuple[int, int, str] | None:
        src = element.attrs.get("src")
        label = f"<img> in {origin}"
        path = self.resolve(src, base_dir=base_dir, label=label)
        if path is None:
            return None
        self._record(path)
        uri = data_uri(_read_bytes(path, label), guess_mime(path))
        rewritten, count = _SRC_ATTR_RE.subn(lambda _: f'src="{uri}"', original, count=1)
        if count != 1:
            raise PackageError(
                f"{label} has a src attribute that cannot be rewritten: {src!r}"
            )
        return (element.start, element.end, rewritten)

    def _rewrite_style(
        self, element: _Element, content: str, *, base_dir: Path, origin: str
    ) -> tuple[int, int, str] | None:
        if not content.strip():
            return None
        css = self.inline_css(
            content, base_dir=base_dir, origin=f"<style> in {origin}"
        )
        if css == content:
            return None
        # Replace the content span only, so the opening tag stays as authored.
        return (element.content_start, element.content_end, _escape_style_text(css))


def _splice(source: str, edits: Sequence[tuple[int, int, str]]) -> str:
    if not edits:
        return source
    pieces: list[str] = []
    cursor = 0
    for start, end, replacement in sorted(edits, key=lambda edit: edit[0]):
        if start < cursor:
            raise PackageError("internal error: overlapping rewrites in the document")
        pieces.append(source[cursor:start])
        pieces.append(replacement)
        cursor = end
    pieces.append(source[cursor:])
    return "".join(pieces)


def package_document(
    entry: Path, *, workspace_root: Path | None = None
) -> PackageResult:
    """Inline every local dependency of `entry` and return the packaged HTML."""
    entry = entry.expanduser()
    if not entry.exists():
        raise PackageError(f"document does not exist: {entry}")
    if not entry.is_file():
        raise PackageError(f"document is not a regular file: {entry}")
    entry = entry.resolve()

    if workspace_root is None:
        root = find_workspace_root(entry)
    else:
        root = workspace_root.expanduser().resolve()
        if not is_workspace_root(root):
            raise PackageError(
                f"{root} is not an OfficeKit workspace: "
                "config.toml or brands/*/brand.json is missing"
            )
    if not _within(entry, root):
        raise PackageError(f"document sits outside the workspace root {root}: {entry}")

    packager = _Packager(root)
    return PackageResult(
        html=packager.package(entry),
        workspace_root=root,
        sources=tuple(packager.sources),
    )


def write_package(result: PackageResult, output: Path) -> Path:
    """Write the packaged HTML, refusing to clobber any file it was built from."""
    output = output.expanduser().resolve()
    if output in result.sources:
        raise PackageError(
            f"output path is one of the document's source files: {output}"
        )
    if output.exists() and not output.is_file():
        raise PackageError(f"output path is not a regular file: {output}")

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PackageError(f"cannot create {output.parent}: {exc}") from exc

    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            handle.write(result.html)
        temporary.replace(output)
    except OSError as exc:
        raise PackageError(f"cannot write {output}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Package an OfficeKit HTML document and its local assets into one "
            "self-contained HTML file."
        )
    )
    parser.add_argument("document", type=Path, help="document entry file (index.html)")
    parser.add_argument("output", type=Path, help="path to write the packaged HTML to")
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="workspace root (default: nearest parent holding config.toml or brands/)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = package_document(args.document, workspace_root=args.workspace_root)
        output = write_package(result, args.output)
    except (PackageError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    inlined = max(len(result.sources) - 1, 0)
    print(f"Inlined {inlined} local file(s) into {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
