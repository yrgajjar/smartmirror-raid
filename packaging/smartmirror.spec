# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SmartMirror RAID.

Build (from the repository root):

    pyinstaller packaging/smartmirror.spec

Produces a single-file executable in ``dist/`` on Windows and Linux, and a
``SmartMirrorRAID.app`` bundle on macOS.
"""

import sys
from pathlib import Path

# When PyInstaller execs this spec, __file__ is defined and points here.
ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 (SPECPATH injected by PyInstaller)

ICON_DIR = ROOT / "packaging" / "icons"
ICON_PNG = ICON_DIR / "icon.png"
ICON_ICO = ICON_DIR / "icon.ico"
ICON_ICNS = ICON_DIR / "icon.icns"

if sys.platform == "win32":
    APP_ICON = str(ICON_ICO) if ICON_ICO.exists() else None
elif sys.platform == "darwin":
    APP_ICON = str(ICON_ICNS) if ICON_ICNS.exists() else None
else:
    APP_ICON = str(ICON_PNG) if ICON_PNG.exists() else None

icon_datas = [(str(ICON_PNG), "smartmirror_assets")] if ICON_PNG.exists() else []

block_cipher = None

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=icon_datas,
    hiddenimports=["watchdog.observers.polling"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SmartMirrorRAID",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="SmartMirrorRAID.app",
        icon=APP_ICON,
        bundle_identifier="com.smartmirror-raid",
        info_plist={
            "LSUIElement": False,
            "CFBundleDisplayName": "SmartMirror RAID",
        },
    )
