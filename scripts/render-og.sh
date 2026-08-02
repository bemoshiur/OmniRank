#!/usr/bin/env bash
# Render the social preview SVG to a 1280x640 PNG.
# Tries rsvg-convert, then headless Chrome. Both produce a GitHub-valid asset.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SVG="$ROOT/.github/assets/og-template.svg"
PNG="$ROOT/.github/assets/og.png"

if command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert -w 1280 -h 640 "$SVG" -o "$PNG"
  echo "rendered with rsvg-convert -> $PNG"
elif [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --headless --disable-gpu --screenshot="$PNG" \
    --window-size=1280,640 --default-background-color=00000000 "file://$SVG"
  echo "rendered with headless Chrome -> $PNG"
else
  echo "No renderer found. Install one:" >&2
  echo "  brew install librsvg" >&2
  exit 1
fi

ls -lh "$PNG"
