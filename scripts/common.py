"""Shared workspace, config, and Jinja helpers for OfficeKit scaffolders."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, StrictUndefined, TemplateError

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
JINJA_SUFFIX = ".j2"
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".htm",
    ".js",
    ".json",
    ".md",
    ".toml",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}
HTML_SUFFIXES = {".html", ".htm", ".xml"}


class ScaffoldError(Exception):
    """Raised when a project cannot be scaffolded or refreshed."""


def _load_catalog():
    path = Path(__file__).resolve().parent / "brand" / "catalog.py"
    spec = importlib.util.spec_from_file_location("officekit_brand_catalog", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ScaffoldError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_catalog = _load_catalog()
BrandCatalogError = _catalog.BrandCatalogError


def _toml_module():
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib
    import tomli

    return tomli


def find_workspace_root(start: Path | None = None) -> Path:
    try:
        return _catalog.find_workspace_root(start or Path.cwd())
    except BrandCatalogError as exc:
        raise ScaffoldError(str(exc)) from exc


def is_workspace_root(path: Path) -> bool:
    return _catalog.is_workspace_root(path)


def load_config(root: Path) -> dict[str, Any]:
    path = root / "config.toml"
    if not path.is_file():
        return {}
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ScaffoldError(f"cannot read {path}: {exc}") from exc
    try:
        data = _toml_module().loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ScaffoldError(f"invalid TOML in {path}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def resolve_brand_id(root: Path, explicit: str | None = None) -> str:
    try:
        return _catalog.resolve_brand_id(root, explicit)
    except BrandCatalogError as exc:
        raise ScaffoldError(str(exc)) from exc


def brand_dir(root: Path, brand_id: str) -> Path:
    return _catalog.brand_dir(root, brand_id)


def brand_name(root: Path, brand_id: str) -> str:
    path = brand_dir(root, brand_id) / "brand.json"
    if not path.is_file():
        return brand_id
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return brand_id
    name = ((data.get("meta") or {}).get("name") or "").strip()
    return name or brand_id


def brand_logo_rel(root: Path, brand_id: str) -> str:
    """Workspace-relative mark used on light grounds, defaulting to assets/logo.svg."""
    path = brand_dir(root, brand_id) / "brand.json"
    fallback = "assets/logo.svg"
    if not path.is_file():
        return fallback
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    logo = data.get("logo")
    if isinstance(logo, str) and logo.strip():
        return logo.strip()
    if not isinstance(logo, dict):
        return fallback
    for size in ("small", "medium", "large"):
        entry = logo.get(size)
        if isinstance(entry, dict):
            value = entry.get("light")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def require_slug(slug: str) -> str:
    cleaned = slug.strip()
    if not SLUG_RE.match(cleaned):
        raise ScaffoldError(
            f"{slug!r} is not a usable slug; use lowercase letters, digits, and hyphens"
        )
    return cleaned


def project_dir(root: Path, slug: str) -> Path:
    return root / "projects" / slug


def relative_to(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        temporary.replace(path)
    except OSError as exc:
        raise ScaffoldError(f"cannot write {path}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def jinja_environment(*, autoescape: bool) -> Environment:
    return Environment(
        undefined=StrictUndefined,
        autoescape=autoescape,
        keep_trailing_newline=True,
    )


def render_string(source: str, context: Mapping[str, Any], *, autoescape: bool) -> str:
    try:
        return jinja_environment(autoescape=autoescape).from_string(source).render(context)
    except TemplateError as exc:
        raise ScaffoldError(f"template render failed: {exc}") from exc


def should_autoescape(path: Path) -> bool:
    name = path.name
    if name.endswith(JINJA_SUFFIX):
        name = name[: -len(JINJA_SUFFIX)]
    return Path(name).suffix.lower() in HTML_SUFFIXES


def destination_name(name: str) -> str:
    if name.endswith(JINJA_SUFFIX):
        return name[: -len(JINJA_SUFFIX)]
    return name


def copy_template_tree(
    source: Path,
    destination: Path,
    context: Mapping[str, Any],
) -> list[Path]:
    """Copy a template directory, rendering ``*.j2`` files into their final names."""
    if not source.is_dir():
        raise ScaffoldError(f"template is missing: {source}")
    written: list[Path] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.name in SKIP_NAMES:
            continue
        relative = path.relative_to(source)
        target = destination.joinpath(*[destination_name(part) for part in relative.parts])
        if path.name.endswith(JINJA_SUFFIX) or path.suffix.lower() in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8")
            if path.name.endswith(JINJA_SUFFIX):
                text = render_string(text, context, autoescape=should_autoescape(path))
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(target, text)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        written.append(target)
    return written


def snapshot_brand(
    root: Path,
    destination: Path,
    brand_id: str,
    *,
    files: list[str],
    directories: list[str],
    target_dir: str = "brand",
) -> Path:
    source = brand_dir(root, brand_id)
    if not (source / "brand.json").is_file():
        raise ScaffoldError(f"brand {brand_id!r} is missing {source / 'brand.json'}")
    target = destination / target_dir
    target.mkdir(parents=True, exist_ok=True)
    for name in files:
        src = source / name
        if not src.is_file():
            raise ScaffoldError(f"brand snapshot source is missing: {src}")
        shutil.copy2(src, target / name)
    for name in directories:
        src = source / name
        if not src.is_dir():
            raise ScaffoldError(f"brand snapshot source is missing: {src}")
        dest = target / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    return target
