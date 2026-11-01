#!/bin/sh
# Installs ClipShrinker for the current user (no root needed).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/512x512/apps"
mkdir -p "$BIN" "$APPS" "$ICONS"
install -m 755 "$DIR/ClipShrinker" "$BIN/ClipShrinker"
install -m 644 "$DIR/clipshrinker.png" "$ICONS/clipshrinker.png"
sed "s|^Exec=ClipShrinker|Exec=$BIN/ClipShrinker|" "$DIR/clipshrinker.desktop" > "$APPS/clipshrinker.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
echo "ClipShrinker installed. Launch it from your app menu or run $BIN/ClipShrinker"
