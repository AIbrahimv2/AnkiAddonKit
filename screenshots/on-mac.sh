#!/bin/bash
# Make an add-on's screenshots on the Mac, wherever you run this from.
#
#   ../anki-addon-kit/screenshots/on-mac.sh [args for tools/screenshots.py]
#
# Run it from an add-on's root. The screenshots need macOS (Anki.app's pages,
# Tahoe's wallpaper, sips, Chromium.app, Anki's Python and the kept copy of
# your collection in ~/anki-collection-copy),
# and they're shown on AnkiGlass's glass, so they're always made on the Mac:
#
# - On the Mac, this just runs tools/screenshots.py.
# - Anywhere else (the Linux machine), it copies this add-on, anki-glass and
#   the kit to a mirror on the Mac (MAC_DIR, under the Mac's home, outside
#   Documents so SSH can reach it), runs tools/screenshots.py there over SSH
#   (MAC_HOST), and copies the PNGs it wrote in docs/ back.
#
# The mirror is only a copy: your repos on the Mac are never touched.
set -euo pipefail

MAC_HOST="${MAC_HOST:-mac}"
MAC_DIR="${MAC_DIR:-anki-shots-mirror}"
ROOT="$(pwd)"
NAME="$(basename "$ROOT")"
KIT="${ANKI_ADDON_KIT:-$(dirname "$ROOT")/anki-addon-kit}"
GLASS="${ANKI_GLASS_REPO:-$(dirname "$ROOT")/anki-glass}"

[ -f tools/screenshots.py ] || { echo "run this from an add-on's root (no tools/screenshots.py here)" >&2; exit 1; }

if [ "$(uname)" = "Darwin" ]; then
  exec python3 tools/screenshots.py "$@"
fi

for d in "$KIT" "$GLASS"; do
  [ -d "$d" ] || { echo "missing $d: clone it next to this add-on" >&2; exit 1; }
done

EXCLUDES=(--exclude .git --exclude node_modules --exclude __pycache__ --exclude dist --exclude .DS_Store)
ssh "$MAC_HOST" "mkdir -p ~/$MAC_DIR"
for d in "$ROOT" "$KIT" "$GLASS"; do
  [ "$d" = "$ROOT" ] && [ "$NAME" = "anki-glass" ] && continue  # synced below as GLASS
  rsync -az --delete "${EXCLUDES[@]}" "$d/" "$MAC_HOST:$MAC_DIR/$(basename "$d")/"
done
[ "$NAME" = "anki-glass" ] && rsync -az --delete "${EXCLUDES[@]}" "$ROOT/" "$MAC_HOST:$MAC_DIR/anki-glass/"

ARGS=""
for a in "$@"; do ARGS+=" $(printf '%q' "$a")"; done
ssh "$MAC_HOST" "zsh -lc 'cd ~/$MAC_DIR/$NAME && python3 tools/screenshots.py$ARGS'"

rsync -az --include '*/' --include '*.png' --exclude '*' "$MAC_HOST:$MAC_DIR/$NAME/docs/" docs/
echo "copied the screenshots back to $NAME/docs/"
