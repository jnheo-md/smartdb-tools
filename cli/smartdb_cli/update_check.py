"""
Cached update notification helpers.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from rich.console import Console

from smartdb_cli import __version__
from smartdb_cli.config import (
    REPO_PYPROJECT_URL,
    SESSION_DIR,
    UPDATE_CHECK_FILE,
    get_update_check_enabled,
    set_update_check_enabled,
)

CHECK_INTERVAL_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 1.5
FALSE_VALUES = {"0", "false", "no", "off", "disable", "disabled"}
TRUE_VALUES = {"1", "true", "yes", "on", "enable", "enabled"}

notice_console = Console(stderr=True)


def _env_flag(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def update_checks_enabled() -> bool:
    """Return whether automatic update checks should run for this process."""
    no_update_check = _env_flag("SMARTDB_NO_UPDATE_CHECK")
    if no_update_check is True:
        return False

    update_check = _env_flag("SMARTDB_UPDATE_CHECK")
    if update_check is not None:
        return update_check

    return get_update_check_enabled()


def set_update_checks_enabled(enabled: bool) -> None:
    """Persist automatic update check preference."""
    set_update_check_enabled(enabled)


def _check_interval_seconds() -> int:
    value = os.environ.get("SMARTDB_UPDATE_CHECK_INTERVAL_SECONDS")
    if not value:
        return CHECK_INTERVAL_SECONDS

    try:
        return max(0, int(value))
    except ValueError:
        return CHECK_INTERVAL_SECONDS


def _read_state() -> dict:
    if not UPDATE_CHECK_FILE.exists():
        return {}

    try:
        data = json.loads(UPDATE_CHECK_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_state(state: dict) -> None:
    try:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        UPDATE_CHECK_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _extract_pyproject_version(text: str) -> str | None:
    match = re.search(r'(?m)^\s*version\s*=\s*["\']([^"\']+)["\']\s*$', text)
    if not match:
        return None
    return match.group(1).strip()


def _version_parts(value: str) -> tuple[int, ...]:
    parts = [int(part) for part in re.findall(r"\d+", value)]
    return tuple(parts[:4])


def is_newer_version(latest_version: str, current_version: str = __version__) -> bool:
    """Return True if latest_version is newer than current_version."""
    latest_parts = _version_parts(latest_version)
    current_parts = _version_parts(current_version)
    max_len = max(len(latest_parts), len(current_parts))
    return latest_parts + (0,) * (max_len - len(latest_parts)) > current_parts + (
        0,
    ) * (max_len - len(current_parts))


def _fetch_latest_version() -> str | None:
    url = os.environ.get("SMARTDB_UPDATE_VERSION_URL", REPO_PYPROJECT_URL)
    request = Request(url, headers={"User-Agent": f"smartdb-cli/{__version__}"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            text = response.read(65536).decode("utf-8", errors="replace")
    except (OSError, TimeoutError, URLError):
        return None

    return _extract_pyproject_version(text)


def _print_update_notice(latest_version: str) -> None:
    notice_console.print(
        "\n"
        f"[yellow]SmartDB CLI {latest_version} is available "
        f"(installed: {__version__}).[/yellow]\n"
        "[dim]Run [bold]smartdb update[/bold] to upgrade, or disable notices with "
        "[bold]smartdb config set-update-check off[/bold].[/dim]"
    )


def maybe_print_update_notice(force: bool = False) -> bool:
    """
    Check GitHub for a newer SmartDB version and print a notice if found.

    Automatic checks are cached, best-effort, and only shown in interactive
    terminals. The command never raises on network failures.
    """
    if not force:
        if not update_checks_enabled():
            return False
        if not sys.stderr.isatty():
            return False

    state = _read_state()
    now = time.time()
    last_checked_at = float(state.get("last_checked_at", 0) or 0)
    if not force and now - last_checked_at < _check_interval_seconds():
        return False

    latest_version = _fetch_latest_version()
    state["last_checked_at"] = now
    if latest_version:
        state["latest_version"] = latest_version
    _write_state(state)

    if latest_version and is_newer_version(latest_version):
        _print_update_notice(latest_version)
        return True

    if force and latest_version:
        notice_console.print(f"[green]SmartDB is up to date (v{__version__}).[/green]")
    elif force:
        notice_console.print("[yellow]Could not check for updates right now.[/yellow]")

    return False
