#!/usr/bin/env bash
# Install extension files to the real UUID dir.
# Then restart the nested shell to pick up changes (close + reopen).
#
# Start nested session once:
#   gnome-shell --devkit --wayland
set -euo pipefail

UUID="openshokz@jfenal.github.com"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"
SRC="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$DEST"
cp "$SRC"/*.js "$SRC"/metadata.json "$SRC"/stylesheet.css "$DEST/"
echo "Installed to $DEST — restart nested shell to reload"
