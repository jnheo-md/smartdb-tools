"""
CLI Configuration
==================
Settings for the SmartDB CLI HTTP client.
"""

import json
import os
from pathlib import Path

# -- Directories & files ------------------------------------------------------
SESSION_DIR: Path = Path.home() / ".smartdb"
SESSION_FILE: Path = SESSION_DIR / "session.json"
CONFIG_FILE: Path = SESSION_DIR / "config.json"
UPDATE_CHECK_FILE: Path = SESSION_DIR / "update_check.json"
VENV_DIR: Path = SESSION_DIR / "venv"
BIN_DIR: Path = VENV_DIR / ("Scripts" if os.name == "nt" else "bin")
MCP_DIR: Path = SESSION_DIR / "mcp-server"
REFERENCE_CACHE_DIR: Path = SESSION_DIR / "reference-cache"
REPO_URL: str = "https://github.com/jnheo-md/smartdb-tools.git"
REPO_TARBALL_URL: str = "https://github.com/jnheo-md/smartdb-tools/archive/refs/heads/master.tar.gz"
REPO_PYPROJECT_URL: str = (
    "https://raw.githubusercontent.com/jnheo-md/smartdb-tools/master/cli/pyproject.toml"
)

# -- API URL ------------------------------------------------------------------
_DEFAULT_API_URL = "https://api.ai.smartstroke.net"


def get_api_url() -> str:
    """Return the API base URL from env var, config file, or default."""
    url = os.environ.get("SMARTDB_API_URL")
    if url:
        return url.rstrip("/")

    data = load_config()
    if data.get("api_url"):
        return str(data["api_url"]).rstrip("/")

    return _DEFAULT_API_URL


def load_config() -> dict:
    """Load the user config file."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config: dict) -> None:
    """Save the user config file."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def set_api_url(url: str) -> None:
    """Save the API URL to the config file."""
    config = load_config()
    config["api_url"] = url.rstrip("/")
    save_config(config)


def get_update_check_enabled() -> bool:
    """Return whether automatic update notices are enabled."""
    value = load_config().get("update_check_enabled", True)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}
    return True


def set_update_check_enabled(enabled: bool) -> None:
    """Enable or disable automatic update notices."""
    config = load_config()
    config["update_check_enabled"] = enabled
    save_config(config)


# -- Export directory ---------------------------------------------------------
EXPORT_DIR: str = os.getcwd()
