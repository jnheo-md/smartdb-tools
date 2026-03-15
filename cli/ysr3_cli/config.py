"""
CLI Configuration
==================
Settings for the YSR3 CLI HTTP client.
"""

import json
import os
from pathlib import Path

# -- Directories & files ------------------------------------------------------
SESSION_DIR: Path = Path.home() / ".ysr3"
SESSION_FILE: Path = SESSION_DIR / "session.json"
CONFIG_FILE: Path = SESSION_DIR / "config.json"

# -- API URL ------------------------------------------------------------------
_DEFAULT_API_URL = "https://api.ai.smartstroke.net"


def get_api_url() -> str:
    """Return the API base URL from env var, config file, or default."""
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


def set_api_url(url: str) -> None:
    """Save the API URL to the config file."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    config: dict = {}
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config = {}

    config["api_url"] = url.rstrip("/")
    CONFIG_FILE.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# -- Export directory ---------------------------------------------------------
EXPORT_DIR: str = os.getcwd()
