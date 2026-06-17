"""Cross-platform "start on boot" / "start on login" management.

This registers the application to launch in tray mode when the user logs in.
Implemented natively per-platform with no extra dependencies:

* Linux  -> XDG autostart .desktop file in ~/.config/autostart
* macOS   -> LaunchAgent plist in ~/Library/LaunchAgents
* Windows -> HKCU\\...\\Run registry value
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from .logger import get_logger
from .version import APP_ID, APP_NAME

log = get_logger("autostart")

_LINUX_DESKTOP = Path.home() / ".config" / "autostart" / f"{APP_ID}.desktop"
_MAC_PLIST = (
    Path.home() / "Library" / "LaunchAgents" / f"com.{APP_ID}.plist"
)
_WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_VALUE = "SmartMirrorRAID"


def _launch_command() -> list[str]:
    """Best-effort command to relaunch the app in tray mode."""
    if getattr(sys, "frozen", False):  # PyInstaller bundle
        return [sys.executable, "--tray"]
    return [sys.executable, "-m", "smartmirror", "tray"]


def _linux_enable() -> None:
    _LINUX_DESKTOP.parent.mkdir(parents=True, exist_ok=True)
    cmd = " ".join(shlex.quote(part) for part in _launch_command())
    _LINUX_DESKTOP.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Exec={cmd}\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Terminal=false\n",
        encoding="utf-8",
    )


def _mac_enable() -> None:
    _MAC_PLIST.parent.mkdir(parents=True, exist_ok=True)
    args = "".join(f"        <string>{a}</string>\n" for a in _launch_command())
    _MAC_PLIST.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "    <key>Label</key>\n"
        f"    <string>com.{APP_ID}</string>\n"
        "    <key>ProgramArguments</key>\n"
        "    <array>\n"
        f"{args}"
        "    </array>\n"
        "    <key>RunAtLoad</key>\n"
        "    <true/>\n"
        "</dict>\n"
        "</plist>\n",
        encoding="utf-8",
    )


def _win_enable() -> None:
    import winreg  # noqa: WPS433 (platform specific import)

    cmd = " ".join(
        f'"{part}"' if " " in part else part for part in _launch_command()
    )
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, _WIN_VALUE, 0, winreg.REG_SZ, cmd)


def _win_disable() -> None:
    import winreg  # noqa: WPS433

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _WIN_VALUE)
    except FileNotFoundError:
        pass


def _win_is_enabled() -> bool:
    import winreg  # noqa: WPS433

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY, 0, winreg.KEY_READ
        ) as key:
            winreg.QueryValueEx(key, _WIN_VALUE)
            return True
    except FileNotFoundError:
        return False


def enable() -> bool:
    """Enable launch on login. Returns True on success."""
    try:
        if sys.platform.startswith("win"):
            _win_enable()
        elif sys.platform == "darwin":
            _mac_enable()
        else:
            _linux_enable()
        log.info("Auto-start enabled")
        return True
    except OSError as exc:
        log.error("Could not enable auto-start: %s", exc)
        return False


def disable() -> bool:
    try:
        if sys.platform.startswith("win"):
            _win_disable()
        elif sys.platform == "darwin":
            _MAC_PLIST.unlink(missing_ok=True)
        else:
            _LINUX_DESKTOP.unlink(missing_ok=True)
        log.info("Auto-start disabled")
        return True
    except OSError as exc:
        log.error("Could not disable auto-start: %s", exc)
        return False


def is_enabled() -> bool:
    if sys.platform.startswith("win"):
        return _win_is_enabled()
    if sys.platform == "darwin":
        return _MAC_PLIST.exists()
    return _LINUX_DESKTOP.exists()


def set_enabled(enabled: bool) -> bool:
    return enable() if enabled else disable()
