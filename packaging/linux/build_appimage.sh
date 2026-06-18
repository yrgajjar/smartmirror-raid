#!/usr/bin/env bash
# Build an AppImage for SmartMirror RAID on Linux.
#
# Usage (from the repository root, on Linux):
#   python -m venv .venv && source .venv/bin/activate
#   pip install -r requirements-dev.txt
#   python packaging/generate_icons.py
#   bash packaging/linux/build_appimage.sh
#
# Result: dist/SmartMirror_RAID-<version>-x86_64.AppImage
#
# Requires appimagetool. If it is not on the PATH the script downloads it to
# dist/tools/. AppImage execution itself needs FUSE; on CI you may need to run
# the resulting file with --appimage-extract-and-run.
set -euo pipefail

VERSION="${SMARTMIRROR_VERSION:-1.0.0}"
ARCH="${SMARTMIRROR_ARCH:-x86_64}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST="$ROOT/dist"
APPDIR="$DIST/SmartMirrorRAID.AppDir"
BIN="$DIST/SmartMirrorRAID"
TOOLS="$DIST/tools"

cd "$ROOT"

if [[ ! -x "$BIN" ]]; then
  echo "==> Building the executable with PyInstaller"
  python packaging/generate_icons.py
  pyinstaller --noconfirm packaging/smartmirror.spec
fi

echo "==> Building the AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/512x512/apps"

install -m 0755 "$BIN" "$APPDIR/usr/bin/SmartMirrorRAID"
install -m 0644 "packaging/icons/icon.png" \
        "$APPDIR/usr/share/icons/hicolor/512x512/apps/smartmirror-raid.png"
cp "packaging/icons/icon.png" "$APPDIR/smartmirror-raid.png"

# Desktop entry (top-level copy is what appimagetool reads).
install -m 0644 "packaging/linux/smartmirror.desktop" \
        "$APPDIR/usr/share/applications/smartmirror-raid.desktop"
cp "$APPDIR/usr/share/applications/smartmirror-raid.desktop" \
   "$APPDIR/smartmirror-raid.desktop"

# AppRun entrypoint.
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/SmartMirrorRAID" "$@"
EOF
chmod 0755 "$APPDIR/AppRun"

# Locate or fetch appimagetool.
APPIMAGETOOL="$(command -v appimagetool || true)"
if [[ -z "$APPIMAGETOOL" ]]; then
  mkdir -p "$TOOLS"
  APPIMAGETOOL="$TOOLS/appimagetool-x86_64.AppImage"
  if [[ ! -x "$APPIMAGETOOL" ]]; then
    echo "==> Downloading appimagetool"
    curl -fsSL -o "$APPIMAGETOOL" \
      "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
  fi
fi

OUT="$DIST/SmartMirror_RAID-${VERSION}-${ARCH}.AppImage"
echo "==> Running appimagetool"
if ! ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$OUT" 2>/dev/null; then
  echo "   (retrying with --appimage-extract-and-run; FUSE may be unavailable)"
  ARCH="$ARCH" "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$OUT"
fi
echo "==> Done: $OUT"
