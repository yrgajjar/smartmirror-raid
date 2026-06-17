"""Cross-platform application directories.

Resolves config / data / log directories for Windows, macOS and Linux without
any third-party dependency.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .version import APP_ID, APP_NAME


def _home() -> Path:
    return Path.home()


def config_dir() -> Path:
    """Directory used to store the user configuration file."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(_home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return _home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(_home() / ".config")
    return Path(base) / APP_ID


def data_dir() -> Path:
    """Directory used to store application state (logs, etc.)."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(_home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return _home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(_home() / ".local" / "share")
    return Path(base) / APP_ID


def log_dir() -> Path:
    return data_dir() / "logs"


def ensure_app_dirs() -> None:
    for path in (config_dir(), data_dir(), log_dir()):
        path.mkdir(parents=True, exist_ok=True)
