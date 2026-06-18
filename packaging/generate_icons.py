"""Render the application icon to PNG / ICO / ICNS files for installers.

The app draws its icon programmatically (``smartmirror.ui.icon.make_app_icon``)
so it never needs a binary asset at runtime. Packaging, however, wants real
icon files embedded in the executable and used by installers, so this script
renders that same icon to ``packaging/icons/``.

Run it whenever the icon design changes::

    python packaging/generate_icons.py

Requires PySide6 (to render) and Pillow (to assemble .ico/.icns).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "packaging" / "icons"
SIZES = [16, 24, 32, 48, 64, 128, 256, 512, 1024]


def _render_pngs() -> dict[int, Path]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT))

    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QApplication

    from smartmirror.ui.icon import make_app_icon

    QApplication.instance() or QApplication([])
    icon = make_app_icon(1024)

    ICON_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[int, Path] = {}
    for size in SIZES:
        pixmap = icon.pixmap(QSize(size, size))
        path = ICON_DIR / f"icon_{size}.png"
        pixmap.save(str(path), "PNG")
        out[size] = path
    # The canonical PNG used by Linux desktop entries.
    icon.pixmap(QSize(512, 512)).save(str(ICON_DIR / "icon.png"), "PNG")
    return out


def _assemble(pngs: dict[int, Path]) -> None:
    from PIL import Image

    images = {size: Image.open(path).convert("RGBA") for size, path in pngs.items()}

    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    images[256].save(
        ICON_DIR / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
    )

    icns_sizes = [16, 32, 64, 128, 256, 512, 1024]
    base = images[1024]
    try:
        base.save(
            ICON_DIR / "icon.icns",
            format="ICNS",
            sizes=[(s, s) for s in icns_sizes],
        )
    except (OSError, ValueError) as exc:  # Pillow ICNS support varies by platform
        print(f"warning: could not write icon.icns ({exc})")


def main() -> int:
    pngs = _render_pngs()
    try:
        _assemble(pngs)
    except ImportError:
        print("warning: Pillow not installed; only PNGs were generated.")
        return 0
    # Remove the intermediate per-size PNGs, keep icon.png/.ico/.icns.
    for path in pngs.values():
        if path.name != "icon.png":
            path.unlink(missing_ok=True)
    print(f"Wrote icons to {ICON_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
