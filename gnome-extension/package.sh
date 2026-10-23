#!/usr/bin/env bash
# Package the openshokz GNOME Shell Extension for submission to extensions.gnome.org.
# Produces <uuid>.zip in the project root with extension files at the zip root level.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
UUID="openshokz@jfenal.github.com"
OUT="$PROJECT_DIR/${UUID}.zip"

# Files to include — exclude dev/install helpers
INCLUDE=(
    extension.js
    indicator.js
    presetMenu.js
    subprocess.js
    stylesheet.css
    metadata.json
)

cd "$SCRIPT_DIR"

# Verify metadata UUID matches
META_UUID=$(python3 -c "import json,sys; print(json.load(open('metadata.json'))['uuid'])")
if [[ "$META_UUID" != "$UUID" ]]; then
    echo "ERROR: metadata.json UUID '$META_UUID' does not match expected '$UUID'" >&2
    exit 1
fi

# Build zip from the project root so files sit at zip root level
rm -f "$OUT"
zip -j "$OUT" "${INCLUDE[@]}"

SIZE=$(du -sh "$OUT" | cut -f1)
echo "Packaged: $OUT ($SIZE)"
echo "Files:"
zipinfo -1 "$OUT"
