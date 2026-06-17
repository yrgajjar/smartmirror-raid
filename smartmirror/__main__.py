"""Module entry point: ``python -m smartmirror``."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    # Support the frozen launcher passing only "--tray".
    argv = sys.argv[1:]
    if argv == ["--tray"]:
        argv = ["tray"]
    raise SystemExit(main(argv))
