#!/usr/bin/env bash
# Build a .deb package for SmartMirror RAID on Debian/Ubuntu.
#
# Usage (from the repository root, on Linux):
#   python -m venv .venv && source .venv/bin/activate
#   pip install -r requirements-dev.txt
#   python packaging/generate_icons.py
#   bash packaging/linux/build_deb.sh
#
# Result: dist/smartmirror-raid_<version>_amd64.deb
set -euo pipefail

VERSION="${SMARTMIRROR_VERSION:-1.0.0}"
ARCH="${SMARTMIRROR_ARCH:-amd64}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST="$ROOT/dist"
PKG="$DIST/deb/smartmirror-raid_${VERSION}_${ARCH}"
BIN="$DIST/SmartMirrorRAID"

cd "$ROOT"

if [[ ! -x "$BIN" ]]; then
  echo "==> Building the executable with PyInstaller"
  python packaging/generate_icons.py
  pyinstaller --noconfirm packaging/smartmirror.spec
fi

echo "==> Laying out the package tree"
rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" \
         "$PKG/opt/smartmirror-raid" \
         "$PKG/usr/bin" \
         "$PKG/usr/share/applications" \
         "$PKG/usr/share/icons/hicolor/512x512/apps" \
         "$PKG/usr/share/doc/smartmirror-raid"

install -m 0755 "$BIN" "$PKG/opt/smartmirror-raid/SmartMirrorRAID"
install -m 0644 "packaging/icons/icon.png" \
        "$PKG/usr/share/icons/hicolor/512x512/apps/smartmirror-raid.png"
install -m 0644 "packaging/linux/smartmirror.desktop" \
        "$PKG/usr/share/applications/smartmirror-raid.desktop"
install -m 0644 "README.md" "$PKG/usr/share/doc/smartmirror-raid/README.md"
install -m 0644 "INSTALL.md" "$PKG/usr/share/doc/smartmirror-raid/INSTALL.md"

# Wrapper on the PATH.
cat > "$PKG/usr/bin/smartmirror-raid" <<'EOF'
#!/bin/sh
exec /opt/smartmirror-raid/SmartMirrorRAID "$@"
EOF
chmod 0755 "$PKG/usr/bin/smartmirror-raid"

INSTALLED_KB="$(du -ks "$PKG" | cut -f1)"

cat > "$PKG/DEBIAN/control" <<EOF
Package: smartmirror-raid
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Yags <https://www.yags.in>
Installed-Size: ${INSTALLED_KB}
Depends: libc6
Description: SmartMirror RAID - software RAID-1 style file mirroring
 Real-time, incremental file mirroring with versioning, selective restore
 and a desktop UI. This is NOT real RAID: it makes software copies of files
 and does not protect against disk hardware failure.
EOF

echo "==> Building the .deb"
mkdir -p "$DIST"
DEB_PATH="$DIST/smartmirror-raid_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$PKG" "$DEB_PATH"
echo "==> Done: $DEB_PATH"
