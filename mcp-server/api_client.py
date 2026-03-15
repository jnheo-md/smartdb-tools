"""
HTTP client for the YSR3 API server.
Shares session/config with the ysr3-cli (~/.ysr3/).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

SESSION_DIR = Path.home() / ".ysr3"
SESSION_FILE = SESSION_DIR / "session.json"
CONFIG_FILE = SESSION_DIR / "config.json"

_DEFAULT_API_URL = "https://api.ai.smartstroke.net"


class APIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def get_api_url() -> str:
    url = os.environ.get("YSR3_API_URL")
    if url:
        return url.rstrip("/")
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if data.get("api_url"):
                return str(data["api_url"]).rstrip("/")
        except (json.JSONDecodeError, OSError):
            pass
    return _DEFAULT_API_URL


def get_token() -> str | None:
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        return data.get("access_token")
    except (json.JSONDecodeError, OSError):
        return None


def is_logged_in() -> bool:
    return get_token() is not None


def get_session_info() -> dict | None:
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        if "uidx" in data:
            return data
        return None
    except (json.JSONDecodeError, OSError):
        return None


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _handle_error(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise APIError(
            "Session expired or invalid. Run 'ysr3 login' in the CLI to re-authenticate.",
            status_code=401,
        )
    detail = f"API error (HTTP {response.status_code})"
    try:
        body = response.json()
        detail = body.get("detail", detail)
    except Exception:
        pass
    raise APIError(detail, status_code=response.status_code)


def get(path: str, params: dict | None = None) -> dict | list:
    url = get_api_url() + path
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=_headers(), params=params)
    if response.status_code >= 400:
        _handle_error(response)
    return response.json()


def post(path: str, json_body: dict | None = None) -> dict | list:
    url = get_api_url() + path
    with httpx.Client(timeout=300.0) as client:
        response = client.post(url, headers=_headers(), json=json_body)
    if response.status_code >= 400:
        _handle_error(response)
    return response.json()


def download(path: str, json_body: dict | None = None) -> tuple[bytes, str]:
    """POST and return (content_bytes, filename)."""
    url = get_api_url() + path
    with httpx.Client(timeout=300.0) as client:
        response = client.post(url, headers=_headers(), json=json_body)
    if response.status_code >= 400:
        _handle_error(response)
    cd = response.headers.get("content-disposition", "")
    filename = "download.xlsx"
    if "filename=" in cd:
        parts = cd.split("filename=")
        if len(parts) > 1:
            filename = parts[1].strip().strip('"')
    filename = os.path.basename(filename)
    if not filename or filename.startswith('.'):
        filename = "download.xlsx"
    return response.content, filename
