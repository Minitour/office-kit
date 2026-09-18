#!/usr/bin/env python3
"""Install or update an isolated OfficeKit workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = "0.1.0"
MARKER = ".officekit-managed.json"


class BootstrapError(Exception):
    """A safe workspace installation cannot be completed."""


def _payload_root() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "workspace"


def _files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_marker(target: Path) -> dict:
    path = target / MARKER
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"invalid {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("files"), dict):
        raise BootstrapError(f"invalid {path}: expected an object with a files map")
    return value


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    shutil.copy2(source, temporary)
    temporary.replace(destination)


def _write_marker(target: Path, files: dict[str, str]) -> None:
    value = {
        "format": 1,
        "plugin": "office-kit",
        "version": VERSION,
        "files": dict(sorted(files.items())),
    }
    path = target / MARKER
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _preflight(
    payload: Path,
    target: Path,
    *,
    previous: dict,
    force: bool,
) -> list[tuple[Path, Path, str]]:
    prior_files = previous.get("files") if previous else {}
    if not isinstance(prior_files, dict):
        prior_files = {}
    planned: list[tuple[Path, Path, str]] = []
    conflicts: list[str] = []

    for source in _files(payload):
        relative = source.relative_to(payload)
        relative_text = relative.as_posix()
        destination = target / relative
        incoming = _sha256(source)
        planned.append((source, destination, incoming))
        if not destination.exists():
            continue
        if not destination.is_file():
            conflicts.append(f"{relative_text}: destination is not a file")
            continue
        current = _sha256(destination)
        prior = prior_files.get(relative_text)
        if current == incoming:
            continue
        if force:
            continue
        if prior is None:
            conflicts.append(
                f"{relative_text}: existing file was not installed by OfficeKit"
            )
        elif current != prior:
            conflicts.append(
                f"{relative_text}: managed file was modified after installation"
            )

    if conflicts:
        detail = "\n".join(f"  - {message}" for message in conflicts)
        raise BootstrapError(
            "refusing to overwrite workspace files:\n"
            f"{detail}\n"
            "Back up the changes or rerun with --force to replace only these "
            "allowlisted managed files."
        )
    return planned


def install_workspace(target: Path, *, force: bool, install: bool) -> None:
    payload = _payload_root()
    if not payload.is_dir():
        raise BootstrapError(f"plugin workspace payload is missing: {payload}")

    target = target.expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise BootstrapError(f"target exists and is not a directory: {target}")
    target.mkdir(parents=True, exist_ok=True)

    marker = _read_marker(target)
    unrelated = any(target.iterdir()) and not marker
    if unrelated and not force:
        raise BootstrapError(
            f"{target} is non-empty and has no {MARKER}; "
            "choose another --target or explicitly use --force"
        )

    planned = _preflight(payload, target, previous=marker, force=force)
    hashes: dict[str, str] = {}
    changed = 0
    for source, destination, digest in planned:
        relative = source.relative_to(payload).as_posix()
        hashes[relative] = digest
        if destination.is_file() and _sha256(destination) == digest:
            continue
        _atomic_copy(source, destination)
        changed += 1

    _write_marker(target, hashes)
    print(
        f"Installed OfficeKit {VERSION} at {target} "
        f"({changed} changed, {len(planned) - changed} unchanged)"
    )

    if not install:
        print("Skipped dependency installation (--no-install)")
        return

    commands = (
        ["uv", "sync"],
        ["npm", "install", "--no-fund", "--no-audit"],
    )
    for command in commands:
        print(f"Running {' '.join(command)}")
        # Windows resolves only .exe from PATH inside CreateProcess, and npm
        # ships as npm.cmd; shutil.which honours PATHEXT and returns the path.
        executable = shutil.which(command[0])
        if executable is None:
            raise BootstrapError(
                f"{command[0]} is required but was not found on PATH"
            )
        try:
            result = subprocess.run(
                [executable, *command[1:]], cwd=target, check=False
            )
        except FileNotFoundError as exc:
            raise BootstrapError(
                f"{command[0]} is required but was not found on PATH"
            ) from exc
        if result.returncode != 0:
            raise BootstrapError(
                f"{' '.join(command)} failed with exit {result.returncode}"
            )


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
        "--target",
        type=Path,
        default=Path.cwd() / "office-kit",
        help="workspace destination (default: ./office-kit)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace conflicting allowlisted payload files only",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="copy files without running uv sync or npm install",
    )
    args = parser.parse_args(argv)
    try:
        install_workspace(
            args.target,
            force=args.force,
            install=not args.no_install,
        )
    except (BootstrapError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
