"""Frozen-build entry point used by PyInstaller.

Running ``SmartMirrorRAID --tray`` starts minimised to the system tray.
"""

from __future__ import annotations

import sys

from smartmirror.cli import main

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv == ["--tray"]:
        argv = ["tray"]
    raise SystemExit(main(argv))
