#!/usr/bin/env bash
set -euo pipefail
UUID="openshokz@jfenal.github.com"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"
mkdir -p "$DEST"
cp -r "$(dirname "$0")"/* "$DEST/"
gnome-extensions enable "$UUID" 2>/dev/null || true
echo "Installed. Restart GNOME Shell (Alt+F2 → r) to activate."
