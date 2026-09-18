"""Shared workspace, config, and Jinja helpers for OfficeKit scaffolders."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

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
IS_WINDOWS = sys.platform.startswith("win")


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


def configure_console() -> None:
    """Make stdout/stderr UTF-8 so ``→`` and ``—`` survive a cp1252 console.

    Windows consoles default to a legacy code page; printing a non-ASCII glyph
    then raises ``UnicodeEncodeError``. Reconfiguring once at CLI entry keeps
    the nicer output everywhere. Streams without ``reconfigure`` (a redirected
    ``StringIO`` in tests) are left alone.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - closed or exotic stream
            pass


def node_bin(name: str) -> str:
    """Resolve ``npm``/``npx``/``node`` to a path ``subprocess`` can launch.

    Windows ``CreateProcess`` resolves only ``.exe`` from ``PATH``; npm and npx
    ship as ``npm.cmd``/``npx.cmd`` shims, so a bare name raises
    ``FileNotFoundError`` even when ``npm --version`` works in the same shell.
    ``shutil.which`` honours ``PATHEXT`` and returns the full path.
    """
    found = shutil.which(name)
    if found is None:
        raise ScaffoldError(
            f"{name} is not installed or not on PATH; install Node.js 22+ "
            "from https://nodejs.org/ and reopen the shell"
        )
    return found


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


def npm_install_workspace(root: Path, workspace_rel: str) -> None:
    """Install a project workspace from the repo root (npm workspaces hoist)."""
    package = root / "package.json"
    if not package.is_file():
        raise ScaffoldError(f"workspace package.json is missing at {package}")
    npm = node_bin("npm")
    try:
        result = subprocess.run(
            [npm, "install", "-w", workspace_rel, "--no-fund", "--no-audit"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ScaffoldError("npm is not installed or not on PATH") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ScaffoldError(
            f"npm install -w {workspace_rel} failed"
            + (f": {detail}" if detail else "")
        )


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _no_window_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if IS_WINDOWS else 0


def pids_listening_on(port: int) -> list[int]:
    """Return PIDs holding TCP ``port`` (best-effort: ``lsof`` or ``netstat``)."""
    if IS_WINDOWS:
        return _pids_listening_on_windows(port)
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []
    if result.returncode not in (0, 1):
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def _pids_listening_on_windows(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            check=False,
            capture_output=True,
            text=True,
            creationflags=_no_window_flags(),
        )
    except FileNotFoundError:
        return []
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        # TCP  0.0.0.0:3030  0.0.0.0:0  LISTENING  1234   (IPv6 shows [::]:3030)
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        if parts[3].upper() != "LISTENING":
            continue
        local_port = parts[1].rsplit(":", 1)[-1]
        if local_port == str(port) and parts[4].isdigit():
            pids.add(int(parts[4]))
    return sorted(pids)


def process_command(pid: int) -> str:
    """Return the command line of ``pid`` (empty when unknown)."""
    if IS_WINDOWS:
        return _process_command_windows(pid)
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _process_command_windows(pid: int) -> str:
    script = (
        f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}')"
        ".CommandLine"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            creationflags=_no_window_flags(),
        )
    except FileNotFoundError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def pid_alive(pid: int) -> bool:
    """True when ``pid`` still runs. Never signals the process."""
    if pid <= 0:
        return False
    if IS_WINDOWS:
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _pid_alive_windows(pid: int) -> bool:
    # os.kill(pid, 0) would TerminateProcess on Windows, so query the handle.
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def kill_pids(pids: Sequence[int], *, grace_seconds: float = 1.5) -> None:
    """Stop ``pids`` (and, on Windows, their process trees)."""
    alive = [pid for pid in pids if pid > 0 and pid_alive(pid)]
    if not alive:
        return
    if IS_WINDOWS:
        _kill_pids_windows(alive)
    else:
        for pid in alive:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            except PermissionError as exc:
                raise ScaffoldError(f"cannot stop pid {pid}: {exc}") from exc
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        alive = [pid for pid in alive if pid_alive(pid)]
        if not alive:
            return
        time.sleep(0.1)
    if IS_WINDOWS:
        _kill_pids_windows(alive)
        return
    for pid in alive:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue


def _kill_pids_windows(pids: Sequence[int]) -> None:
    # The recorded pid is usually the npx.cmd shim (cmd.exe); /T takes the
    # node child with it, /F because dev servers ignore a polite close.
    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
                creationflags=_no_window_flags(),
            )
        except FileNotFoundError as exc:  # pragma: no cover - taskkill is core
            raise ScaffoldError(f"cannot stop pid {pid}: {exc}") from exc


def claim_port(
    preferred: int,
    *,
    reclaimable: Sequence[str],
    max_offset: int = 20,
) -> tuple[int, list[str]]:
    """Return an available port, killing reclaimable holders of ``preferred``.

    ``reclaimable`` is a list of substrings; if every listener's command line
    matches at least one, those processes are stopped and ``preferred`` is
    reused. Otherwise the next free port in ``preferred..preferred+max_offset``
    is chosen.
    """
    notes: list[str] = []
    holders = pids_listening_on(preferred)
    if not holders:
        return preferred, notes

    commands = {pid: process_command(pid) for pid in holders}
    reclaimable_l = [token.lower() for token in reclaimable]
    all_reclaimable = True
    for pid, command in commands.items():
        lowered = command.lower()
        if not any(token in lowered for token in reclaimable_l):
            all_reclaimable = False
            notes.append(
                f"port {preferred} held by pid {pid} ({command or 'unknown'}); "
                "not reclaiming"
            )
            break

    if all_reclaimable:
        kill_pids(holders)
        notes.append(
            f"stopped {len(holders)} process(es) on port {preferred}: "
            + ", ".join(str(pid) for pid in holders)
        )
        if port_is_free(preferred):
            return preferred, notes

    for offset in range(1, max_offset + 1):
        candidate = preferred + offset
        if port_is_free(candidate) and not pids_listening_on(candidate):
            notes.append(f"using port {candidate} because {preferred} is busy")
            return candidate, notes

    raise ScaffoldError(
        f"no free port in {preferred}..{preferred + max_offset}; "
        + ("; ".join(notes) if notes else "all candidates busy")
    )


def wait_http_ok(
    url: str,
    *,
    timeout_seconds: float = 45.0,
    poll_seconds: float = 0.4,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if 200 <= getattr(response, "status", 200) < 300:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(poll_seconds)
    return False


def write_pidfile(path: Path, pid: int, *, port: int, slug: str) -> None:
    atomic_write(path, f"pid={pid}\nport={port}\nslug={slug}\n")


def read_pidfile(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def spawn_detached(
    command: Sequence[str],
    *,
    cwd: Path,
    log_path: Path,
) -> int:
    """Start ``command`` detached; return its PID. Logs go to ``log_path``."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")
    popen_kwargs: dict[str, Any] = {}
    if IS_WINDOWS:
        # A new process group so Ctrl+C in this shell does not reach the
        # server, and no console window so the shim runs silently. The child
        # outlives this interpreter; ``kill_pids`` tears the tree down later.
        popen_kwargs["creationflags"] = int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        ) | _no_window_flags()
    else:
        popen_kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            **popen_kwargs,
        )
    except OSError as exc:
        log_handle.close()
        raise ScaffoldError(f"failed to start {' '.join(command)}: {exc}") from exc
    log_handle.close()
    return int(process.pid)


def stop_pidfile(path: Path) -> list[str]:
    """Stop the process recorded in ``path`` and remove the file."""
    notes: list[str] = []
    data = read_pidfile(path)
    raw_pid = data.get("pid")
    if raw_pid and raw_pid.isdigit():
        pid = int(raw_pid)
        if not pid_alive(pid):
            notes.append(f"pid {pid} already stopped")
        else:
            kill_pids([pid])
            notes.append(f"stopped pid {pid}")
    path.unlink(missing_ok=True)
    return notes
