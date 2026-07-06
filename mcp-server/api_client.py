"""
HTTP client for the SmartDB API server.
Shares session/config with the smartdb-cli (~/.smartdb/).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

SESSION_DIR = Path.home() / ".smartdb"
SESSION_FILE = SESSION_DIR / "session.json"
CONFIG_FILE = SESSION_DIR / "config.json"

_DEFAULT_API_URL = "https://api.ai.smartstroke.net"
_EXCLUDED_TEST_HOSPITAL_CODES = frozenset({"SMU"})
_EXCLUDED_TEST_HOSPITAL_HIDXS = frozenset({"4"})
_EXCLUDED_TEST_HOSPITAL_NAMES = frozenset({"스마트 병원"})
_PATH_HOSPITAL_SEGMENTS = {
    ("schema", "tables"): 2,
    ("schema", "search"): 2,
    ("schema", "variable"): 2,
    ("schema", "table-vars"): 2,
    ("schema", "sections"): 2,
    ("schema", "section-vars"): 2,
    ("schema", "describe"): 2,
    ("anon", "tables"): 2,
    ("anon", "patient"): 2,
    ("clot", "patients"): 2,
    ("clot", "composition"): 2,
    ("clot", "summary"): 2,
}


class APIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def include_test_hospitals() -> bool:
    return os.environ.get("SMARTDB_INCLUDE_TEST_HOSPITALS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def is_excluded_test_hospital(value: object) -> bool:
    if include_test_hospitals() or value is None:
        return False
    normalized = str(value).strip()
    return (
        normalized.upper() in _EXCLUDED_TEST_HOSPITAL_CODES
        or normalized in _EXCLUDED_TEST_HOSPITAL_HIDXS
        or normalized in _EXCLUDED_TEST_HOSPITAL_NAMES
    )


def filter_visible_hospitals(hospitals: list[dict]) -> list[dict]:
    if include_test_hospitals():
        return hospitals
    return [
        hospital
        for hospital in hospitals
        if not (
            is_excluded_test_hospital(hospital.get("code"))
            or is_excluded_test_hospital(hospital.get("hidx"))
            or is_excluded_test_hospital(hospital.get("name"))
        )
    ]


def excluded_hospital_message(value: object) -> str:
    return (
        f"Hospital '{value}' is a SmartDB test hospital and is hidden by "
        "smartdb-tools. Set SMARTDB_INCLUDE_TEST_HOSPITALS=1 to access it "
        "for maintenance."
    )


def get_api_url() -> str:
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
            "Session expired or invalid. Run 'smartdb login' in the CLI to re-authenticate.",
            status_code=401,
        )
    detail = f"API error (HTTP {response.status_code})"
    try:
        body = response.json()
        detail = body.get("detail", detail)
    except Exception:
        pass
    raise APIError(detail, status_code=response.status_code)


def _hospital_from_path(path: str) -> str | None:
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None
    index = _PATH_HOSPITAL_SEGMENTS.get((parts[0], parts[1]))
    if index is None or len(parts) <= index:
        return None
    return parts[index]


def _hospital_from_body(value: object) -> str | None:
    if isinstance(value, dict):
        for key in ("hospital", "hospital_code"):
            if key in value and is_excluded_test_hospital(value[key]):
                return str(value[key])
        for nested in value.values():
            found = _hospital_from_body(nested)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _hospital_from_body(item)
            if found:
                return found
    return None


def _check_test_hospital_access(path: str, body: object | None = None) -> None:
    hospital = _hospital_from_path(path) or _hospital_from_body(body)
    if hospital and is_excluded_test_hospital(hospital):
        raise APIError(excluded_hospital_message(hospital), status_code=400)


def _filter_response(path: str, payload: dict | list) -> dict | list:
    if path == "/schema/hospitals" and isinstance(payload, list):
        return filter_visible_hospitals(payload)
    return payload


def get(path: str, params: dict | None = None) -> dict | list:
    _check_test_hospital_access(path)
    url = get_api_url() + path
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=_headers(), params=params)
    if response.status_code >= 400:
        _handle_error(response)
    return _filter_response(path, response.json())


def post(path: str, json_body: dict | None = None) -> dict | list:
    _check_test_hospital_access(path, json_body)
    url = get_api_url() + path
    with httpx.Client(timeout=300.0) as client:
        response = client.post(url, headers=_headers(), json=json_body)
    if response.status_code >= 400:
        _handle_error(response)
    return _filter_response(path, response.json())


def download(path: str, json_body: dict | None = None) -> tuple[bytes, str]:
    """POST and return (content_bytes, filename)."""
    _check_test_hospital_access(path, json_body)
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
