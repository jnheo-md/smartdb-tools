"""HTTP client for the SmartDB API server."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

SESSION_DIR = Path.home() / ".smartdb"
SESSION_FILE = SESSION_DIR / "session.json"
CONFIG_FILE = SESSION_DIR / "config.json"

_DEFAULT_API_URL = "https://api.ai.smartstroke.net"


class APIError(Exception):
    """Raised when an API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _get_api_url() -> str:
    """Return the API base URL from env var, config file, or session."""
    import os

    url = os.environ.get("SMARTDB_API_URL")
    if url:
        return url.rstrip("/")

    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if data.get("api_url"):
                return str(data["api_url"]).rstrip("/")
        except (json.JSONDecodeError, OSError):
            pass

    if SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            if data.get("api_url"):
                return str(data["api_url"]).rstrip("/")
        except (json.JSONDecodeError, OSError):
            pass

    return _DEFAULT_API_URL


def _get_token() -> str | None:
    """Read the JWT access token from the session file."""
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        return data.get("access_token")
    except (json.JSONDecodeError, OSError):
        return None


def _build_headers() -> dict[str, str]:
    """Build request headers with Authorization if a token exists."""
    headers: dict[str, str] = {"Accept": "application/json"}
    token = _get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _handle_error_response(response: httpx.Response) -> None:
    """Raise an APIError from a non-2xx response."""
    if response.status_code == 401:
        raise APIError(
            "Session expired or invalid. Run [bold]smartdb login[/bold] to authenticate.",
            status_code=401,
        )
    if response.status_code == 403:
        detail = "Access denied."
        try:
            body = response.json()
            detail = body.get("detail", detail)
        except Exception:
            pass
        raise APIError(detail, status_code=403)

    # Generic error
    detail = f"API error (HTTP {response.status_code})"
    try:
        body = response.json()
        detail = body.get("detail", detail)
    except Exception:
        pass
    raise APIError(detail, status_code=response.status_code)


def get(path: str, params: dict | None = None) -> dict | list:
    """Send a GET request to the API and return the JSON response."""
    url = _get_api_url() + path
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(url, headers=_build_headers(), params=params)
    except httpx.ConnectError:
        raise APIError(
            f"Cannot connect to the API server at {_get_api_url()}. "
            "Is the server running? Use 'smartdb config show' to check the API URL."
        )
    except httpx.TimeoutException:
        raise APIError("Request timed out. The server may be overloaded.")

    if response.status_code >= 400:
        _handle_error_response(response)

    return response.json()


def post(path: str, json_body: dict | None = None) -> dict | list:
    """Send a POST request to the API and return the JSON response."""
    url = _get_api_url() + path
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, headers=_build_headers(), json=json_body)
    except httpx.ConnectError:
        raise APIError(
            f"Cannot connect to the API server at {_get_api_url()}. "
            "Is the server running? Use 'smartdb config show' to check the API URL."
        )
    except httpx.TimeoutException:
        raise APIError("Request timed out. The server may be overloaded.")

    if response.status_code >= 400:
        _handle_error_response(response)

    return response.json()


def download(path: str, json_body: dict | None = None, save_path: Path | None = None) -> Path:
    """Send a POST request and save the response body as a file.

    Returns the path to the saved file.
    """
    url = _get_api_url() + path
    try:
        with httpx.Client(timeout=300.0) as client:
            response = client.post(url, headers=_build_headers(), json=json_body)
    except httpx.ConnectError:
        raise APIError(
            f"Cannot connect to the API server at {_get_api_url()}. "
            "Is the server running? Use 'smartdb config show' to check the API URL."
        )
    except httpx.TimeoutException:
        raise APIError("Request timed out. The export may be too large.")

    if response.status_code >= 400:
        _handle_error_response(response)

    # Determine save path from Content-Disposition header if not provided
    if save_path is None:
        cd = response.headers.get("content-disposition", "")
        filename = "download.xlsx"
        if "filename=" in cd:
            parts = cd.split("filename=")
            if len(parts) > 1:
                filename = parts[1].strip().strip('"')
        import os
        filename = os.path.basename(filename)
        if not filename or filename.startswith('.'):
            filename = "download.xlsx"
        from smartdb_cli.config import EXPORT_DIR

        save_path = Path(EXPORT_DIR) / filename

    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(response.content)
    return save_path


def upload_and_download(
    path: str,
    file_path: Path,
    data: dict | None = None,
    save_path: Path | None = None,
) -> Path:
    """Upload a file via multipart POST and save the response as a file.

    Returns the path to the saved file.
    """
    url = _get_api_url() + path
    headers = _build_headers()
    # Remove Accept: application/json for file upload since we expect a file back
    headers.pop("Accept", None)

    try:
        with httpx.Client(timeout=300.0) as client:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                response = client.post(url, headers=headers, files=files, data=data)
    except httpx.ConnectError:
        raise APIError(
            f"Cannot connect to the API server at {_get_api_url()}. "
            "Is the server running? Use 'smartdb config show' to check the API URL."
        )
    except httpx.TimeoutException:
        raise APIError("Request timed out. The merge may be too large.")

    if response.status_code >= 400:
        _handle_error_response(response)

    if save_path is None:
        cd = response.headers.get("content-disposition", "")
        filename = "merged.xlsx"
        if "filename=" in cd:
            parts = cd.split("filename=")
            if len(parts) > 1:
                filename = parts[1].strip().strip('"')
        import os
        filename = os.path.basename(filename)
        if not filename or filename.startswith('.'):
            filename = "merged.xlsx"
        from smartdb_cli.config import EXPORT_DIR

        save_path = Path(EXPORT_DIR) / filename

    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(response.content)
    return save_path
