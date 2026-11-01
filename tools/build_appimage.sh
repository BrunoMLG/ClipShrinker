#!/bin/sh
# Package the PyInstaller Linux build into an AppImage.
#
# Usage (on Linux, from the project root, after `pyinstaller ClipShrinker.spec`):
#   tools/build_appimage.sh [output-file]
#
# Downloads appimagetool on first use. Set APPIMAGETOOL to use an existing copy.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCH="${ARCH:-$(uname -m)}"
OUT="${1:-$ROOT/dist/ClipShrinker-linux-$ARCH.AppImage}"
BUILD="$ROOT/build/appimage"
APPDIR="$BUILD/ClipShrinker.AppDir"

if [ ! -x "$ROOT/dist/ClipShrinker/ClipShrinker" ]; then
    echo "dist/ClipShrinker/ClipShrinker not found - run 'pyinstaller ClipShrinker.spec' first." >&2
    exit 1
fi

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib"
cp -a "$ROOT/dist/ClipShrinker" "$APPDIR/usr/lib/ClipShrinker"
cp "$ROOT/assets/clipshrinker.desktop" "$APPDIR/clipshrinker.desktop"
cp "$ROOT/clipshrinker/resources/icon.png" "$APPDIR/clipshrinker.png"
ln -sf clipshrinker.png "$APPDIR/.DirIcon"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/ClipShrinker/ClipShrinker" "$@"
EOF
chmod +x "$APPDIR/AppRun"

TOOL="${APPIMAGETOOL:-$BUILD/appimagetool-$ARCH.AppImage}"
if [ ! -x "$TOOL" ]; then
    echo "Downloading appimagetool..."
    curl -fsSL -o "$TOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
    chmod +x "$TOOL"
fi

# Extract-and-run lets appimagetool work on machines (and CI runners) without FUSE.
APPIMAGE_EXTRACT_AND_RUN=1 ARCH="$ARCH" "$TOOL" --no-appstream "$APPDIR" "$OUT"
echo "Built $OUT"
