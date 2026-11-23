#!/bin/bash
# Put an add-on's current code into the Mac's real Anki, from the Linux machine.
#
#   ../anki-addon-kit/tools/to-mac.sh [--restart]        # from an add-on's root
#   tools/to-mac.sh [--restart] anki-skim anki-stepwise  # from the kit, by repo name
#
# For each add-on: builds its page (web/ into src/web/, when it has one and
# npm is here), then mirrors src/ and CHANGELOG.md to LIVE_DIR/<repo> under
# the Mac's home (Documents/Projects/anki/work/addons-live). Anki loads
# it from there: the add-on's folder in addons21 is a symlink to that copy.
#
# The first time, that symlink still points at the Mac's old checkout
# (~/Documents/Projects/<repo>/src). It's moved to the live copy, and the
# add-on's settings (meta.json) and user_files come along, so nothing you set
# in Anki is lost. Anki keeps writing those into the live copy, and they're
# never overwritten or deleted from here.
#
# Anki reads an add-on's Python when it starts, so it needs a restart to show
# the change: --restart quits Anki (it saves as it closes) and opens it again.
# Without it, this says to restart.
set -euo pipefail

MAC_HOST="${MAC_HOST:-mac}"
LIVE_DIR="${LIVE_DIR:-Documents/Projects/anki/work/addons-live}"
ADDONS='Library/Application Support/Anki2/addons21'
PROJECTS="$(cd "$(dirname "$0")/../.." && pwd)"

restart=0
repos=()
for a in "$@"; do
  case "$a" in
    --restart) restart=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) repos+=("$a") ;;
  esac
done
if [ ${#repos[@]} -eq 0 ]; then
  [ -f src/manifest.json ] || { echo "run this from an add-on's root, or name the repos" >&2; exit 1; }
  repos=("$(basename "$(pwd)")")
fi

if [ "$(uname)" = "Darwin" ]; then
  echo "this is for the Linux machine: on the Mac, Anki already loads the repos it links to" >&2
  exit 1
fi
ssh -o ConnectTimeout=8 "$MAC_HOST" true 2>/dev/null \
  || { echo "can't reach the Mac ($MAC_HOST): it's asleep, closed or off Tailscale" >&2; exit 1; }

for repo in "${repos[@]}"; do
  dir="$PROJECTS/$repo"
  [ -f "$dir/src/manifest.json" ] || { echo "$repo: no src/manifest.json in $dir" >&2; exit 1; }

  if [ -f "$dir/web/package.json" ] && command -v npm >/dev/null 2>&1; then
    [ -d "$dir/web/node_modules" ] || npm --prefix "$dir/web" ci --silent
    npm --prefix "$dir/web" run build --silent >/dev/null
  fi

  ssh "$MAC_HOST" "mkdir -p ~/$LIVE_DIR/$repo"
  # --delete never touches what's excluded, so Anki's own files stay.
  rsync -az --delete \
    --exclude __pycache__ --exclude '*.pyc' --exclude .DS_Store \
    --exclude meta.json --exclude user_files \
    "$dir/src/" "$MAC_HOST:$LIVE_DIR/$repo/"
  [ -f "$dir/CHANGELOG.md" ] && rsync -az "$dir/CHANGELOG.md" "$MAC_HOST:$LIVE_DIR/$repo/"

  # Point Anki's folder for it at the live copy: the folder that links to this
  # repo's src (its name is what Anki keys its settings by), or a new one
  # named after the repo.
  ssh "$MAC_HOST" "bash -s" <<EOF
set -euo pipefail
cd ~/"$ADDONS"
live=~/"$LIVE_DIR/$repo"
link=""
for f in *; do
  [ -L "\$f" ] || continue
  t="\$(readlink "\$f")"
  case "\$t" in */"$repo"/src|*/"$repo"/src/|"\$live") link="\$f"; break ;; esac
done
if [ -z "\$link" ]; then
  [ -e "$repo" ] && { echo "$repo: addons21/$repo exists and isn't a link to it; leaving it alone" >&2; exit 1; }
  link="$repo"
elif [ "\$(readlink "\$link")" != "\$live" ]; then
  old="\$(readlink "\$link")"
  [ -f "\$old/meta.json" ] && [ ! -f "\$live/meta.json" ] && cp -p "\$old/meta.json" "\$live/"
  [ -d "\$old/user_files" ] && [ ! -e "\$live/user_files" ] && cp -Rp "\$old/user_files" "\$live/"
  echo "$repo: Anki's addons21/\$link now loads ~/$LIVE_DIR/$repo (it was \$old)"
fi
ln -sfn "\$live" "\$link"
EOF
  echo "$repo: on the Mac ($(cd "$dir" && git log -1 --format=%h)$(cd "$dir" && [ -n "$(git status --porcelain)" ] && echo ', with uncommitted changes'))"
done

if [ "$restart" = 1 ]; then
  ssh "$MAC_HOST" 'osascript -e "quit app \"Anki\"" >/dev/null 2>&1 || true
    for i in $(seq 1 40); do pgrep -fq "Anki.app/Contents/MacOS/" || break; sleep 0.5; done
    open -a Anki'
  echo "Anki restarted on the Mac"
else
  echo "restart Anki on the Mac to load it (or run this with --restart)"
fi
