"""Resolve named brands under ``brands/<id>/``.

A workspace can hold any number of identities. Each one is a directory
``brands/<id>/`` whose ``brand.json`` is canonical and whose ``BRAND.md``,
``tokens.css``, and ``frame.md`` are generated. ``config.toml`` ``[brand]
default`` picks the identity used when a project does not name one.
"""

from __future__ import annotations

import re
from pathlib import Path

BRANDS_DIRNAME = "brands"
BRAND_FILE = "brand.json"
BRAND_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DEFAULT_KEY_RE = re.compile(
    r"^\[brand\][^\[]*?^default\s*=\s*[\"']([^\"']+)[\"']",
    re.MULTILINE | re.DOTALL,
)


class BrandCatalogError(Exception):
    """The workspace has no usable brand, or the requested id is missing."""


def is_workspace_root(path: Path) -> bool:
    if (path / "config.toml").is_file():
        return True
    brands = path / BRANDS_DIRNAME
    return brands.is_dir() and any(brands.glob(f"*/{BRAND_FILE}"))


def find_workspace_root(start: Path) -> Path:
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if is_workspace_root(candidate):
            return candidate
    raise BrandCatalogError(
        f"cannot find the workspace root above {start}: no parent directory "
        f"contains config.toml or {BRANDS_DIRNAME}/*/{BRAND_FILE}"
    )


def list_brand_ids(root: Path) -> list[str]:
    brands = root / BRANDS_DIRNAME
    if not brands.is_dir():
        return []
    ids: list[str] = []
    for child in sorted(brands.iterdir()):
        if (
            child.is_dir()
            and BRAND_ID_RE.match(child.name)
            and (child / BRAND_FILE).is_file()
        ):
            ids.append(child.name)
    return ids


def brand_dir(root: Path, brand_id: str) -> Path:
    return root / BRANDS_DIRNAME / brand_id


def configured_default(root: Path) -> str | None:
    config = root / "config.toml"
    if not config.is_file():
        return None
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        import tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            data = None
        if isinstance(data, dict):
            table = data.get("brand")
            if isinstance(table, dict):
                value = table.get("default")
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return None
    match = DEFAULT_KEY_RE.search(text)
    return match.group(1).strip() if match else None


def default_brand_id(root: Path) -> str:
    ids = list_brand_ids(root)
    configured = configured_default(root)
    if configured:
        if configured not in ids:
            raise BrandCatalogError(
                f"config.toml [brand] default is {configured!r}, but "
                f"{BRANDS_DIRNAME}/{configured}/{BRAND_FILE} is missing"
            )
        return configured
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise BrandCatalogError(
            f"no brands under {BRANDS_DIRNAME}/; create brands/<id>/brand.json"
        )
    raise BrandCatalogError(
        f"multiple brands ({', '.join(ids)}) and no [brand] default in config.toml"
    )


def resolve_brand_id(root: Path, explicit: str | None) -> str:
    if explicit is None or not explicit.strip():
        return default_brand_id(root)
    brand_id = explicit.strip()
    if not BRAND_ID_RE.match(brand_id):
        raise BrandCatalogError(
            f"{brand_id!r} is not a usable brand id; use lowercase letters, "
            "digits, and hyphens"
        )
    if not (brand_dir(root, brand_id) / BRAND_FILE).is_file():
        known = ", ".join(list_brand_ids(root)) or "(none)"
        raise BrandCatalogError(
            f"brand {brand_id!r} does not exist under {BRANDS_DIRNAME}/; "
            f"known: {known}"
        )
    return brand_id
