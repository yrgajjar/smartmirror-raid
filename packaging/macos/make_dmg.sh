#!/usr/bin/env bash
# Build a distributable SmartMirror RAID .dmg on macOS.
#
# Usage (from the repository root, on macOS):
#   python -m venv .venv && source .venv/bin/activate
#   pip install -r requirements-dev.txt
#   python packaging/generate_icons.py
#   bash packaging/macos/make_dmg.sh
#
# Result: dist/SmartMirrorRAID-<version>.dmg
set -euo pipefail

APP_NAME="SmartMirror RAID"
VERSION="${SMARTMIRROR_VERSION:-1.0.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST="$ROOT/dist"
APP_BUNDLE="$DIST/SmartMirrorRAID.app"
DMG_PATH="$DIST/SmartMirrorRAID-$VERSION.dmg"
STAGING="$DIST/dmg-staging"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "error: this script must be run on macOS (uses hdiutil)." >&2
  exit 1
fi

cd "$ROOT"

echo "==> Building the .app bundle with PyInstaller"
python packaging/generate_icons.py
pyinstaller --noconfirm packaging/smartmirror.spec

if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "error: expected app bundle not found at $APP_BUNDLE" >&2
  exit 1
fi

echo "==> Staging the disk image contents"
rm -rf "$STAGING" "$DMG_PATH"
mkdir -p "$STAGING"
cp -R "$APP_BUNDLE" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

echo "==> Creating $DMG_PATH"
if command -v create-dmg >/dev/null 2>&1; then
  # Prettier layout if the optional 'create-dmg' tool is installed.
  create-dmg \
    --volname "$APP_NAME" \
    --volicon "packaging/icons/icon.icns" \
    --window-size 540 380 \
    --icon-size 110 \
    --icon "SmartMirrorRAID.app" 150 180 \
    --app-drop-link 390 180 \
    "$DMG_PATH" "$STAGING" || {
      echo "create-dmg failed; falling back to hdiutil"; rm -f "$DMG_PATH";
      hdiutil create -volname "$APP_NAME" -srcfolder "$STAGING" -ov -format UDZO "$DMG_PATH";
    }
else
  hdiutil create -volname "$APP_NAME" -srcfolder "$STAGING" -ov -format UDZO "$DMG_PATH"
fi

rm -rf "$STAGING"
echo "==> Done: $DMG_PATH"
