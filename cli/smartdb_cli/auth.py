"""
Authentication & Session Management
=====================================
Handles user login/logout and session persistence for the SmartDB CLI.
Uses the API server for authentication instead of direct DB access.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from smartdb_cli.config import SESSION_DIR, SESSION_FILE, get_api_url
from smartdb_cli.formatting import print_error


class AuthenticationError(Exception):
    """Raised when login credentials are invalid."""


def login(email: str, password: str) -> dict:
    """Authenticate via the API server and save the session.

    Returns the session dict on success, raises AuthenticationError on failure.
    """
    from smartdb_cli import api_client
    from smartdb_cli.api_client import APIError

    try:
        result = api_client.post("/auth/login", json_body={
            "email": email,
            "password": password,
        })
    except APIError as exc:
        if exc.status_code == 401:
            raise AuthenticationError("Invalid email or password.")
        raise AuthenticationError(str(exc))

    user = result.get("user", {})
    session = {
        "access_token": result["access_token"],
        "uidx": user.get("uidx"),
        "level": user.get("level"),
        "hidx": user.get("hidx"),
        "email": user.get("email"),
        "uname": user.get("uname"),
        "description": user.get("description", ""),
        "manager_perm": user.get("manager_perm", 0),
        "api_url": get_api_url(),
        "login_time": datetime.now().isoformat(),
    }

    _save_session(session)
    return session


def logout() -> None:
    """Delete the current session file."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def get_current_user() -> dict | None:
    """Read and return the current session, or None if not logged in."""
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "uidx" not in data:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def verify_token() -> dict | None:
    """Call GET /auth/me to validate the token is still valid.

    Returns the user dict from the server, or None if invalid.
    """
    from smartdb_cli import api_client
    from smartdb_cli.api_client import APIError

    try:
        result = api_client.get("/auth/me")
        return result
    except APIError:
        return None


def require_auth() -> dict:
    """Return the current session or print an error and exit."""
    user = get_current_user()
    if user is None:
        print_error("Not logged in. Run [bold]smartdb login[/bold] first.")
        sys.exit(1)
    return user


def get_user_level_label(level: int) -> str:
    """Return a human-readable label for the user level code."""
    labels = {1: "User", 2: "Manager", 3: "Super Admin"}
    return labels.get(level, f"Unknown ({level})")


def _save_session(session: dict) -> None:
    """Write session data to disk with restricted permissions (atomic)."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(SESSION_DIR, 0o700)

    tmp_path = SESSION_FILE.with_suffix(".tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps(session, ensure_ascii=False, indent=2).encode("utf-8"))
    finally:
        os.close(fd)
    os.rename(str(tmp_path), str(SESSION_FILE))
