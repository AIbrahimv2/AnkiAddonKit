#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Copy the kit into an add-on's repo, or check that its copy is current.

    python3 sync.py ../anki-tag-queue ../anki-skim   # copy the kit in
    python3 sync.py --check ../anki-tag-queue        # exit 1 if it differs

An add-on gets:
  src/kit/      the Python (py/), catalog.json and the built page (py/web/)
  web/src/kit/  the shared styles and React components (web/), if the
                add-on has a web page of its own (web/src/)

Each add-on carries its own copy because Anki add-ons can't depend on one
another. Build the page first (`npm run build`) when standalone/ or web/
changed: sync refuses a page older than its sources.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys

KIT = os.path.dirname(os.path.abspath(__file__))

PY_FILES = ["__init__.py", "family.py", "changelog.py", "settings.py", "page.py"]
PAGE_FILES = ["page.js", "page.css"]
WEB_FILES = [
    "tokens.css", "controls.css", "dialog.css", "kit.css",
    "controls.tsx", "settings.tsx", "AddonDialog.tsx", "markdown.tsx", "Signature.tsx", "types.ts",
]

NOTE = """# Vendored from anki-addon-kit

This folder is a copy of part of
[AnkiAddonKit](https://github.com/AIbrahimv2/AnkiAddonKit), what AIbrahimv2's
Anki add-ons share (checked out beside the add-ons as `anki-addon-kit`).
Don't edit it here: change the kit and run `python3 sync.py <this repo>`
there. `sync.py --check` says whether this copy is current.
"""


def plan(repo: str) -> list[tuple[str, str]]:
    """(source, destination) for every file the add-on gets."""
    pairs = [(os.path.join(KIT, "py", f), os.path.join(repo, "src", "kit", f)) for f in PY_FILES]
    pairs.append((os.path.join(KIT, "catalog.json"), os.path.join(repo, "src", "kit", "catalog.json")))
    pairs += [(os.path.join(KIT, "py", "web", f), os.path.join(repo, "src", "kit", "web", f)) for f in PAGE_FILES]
    if os.path.isdir(os.path.join(repo, "web", "src")):
        pairs += [(os.path.join(KIT, "web", f), os.path.join(repo, "web", "src", "kit", f)) for f in WEB_FILES]
    return pairs


def kit_dirs(repo: str) -> list[str]:
    dirs = [os.path.join(repo, "src", "kit")]
    if os.path.isdir(os.path.join(repo, "web", "src")):
        dirs.append(os.path.join(repo, "web", "src", "kit"))
    return dirs


def page_is_stale() -> bool:
    built = [os.path.join(KIT, "py", "web", f) for f in PAGE_FILES]
    if not all(os.path.exists(p) for p in built):
        return True
    oldest = min(os.path.getmtime(p) for p in built)
    for folder in ("web", "standalone"):
        for root, _dirs, files in os.walk(os.path.join(KIT, folder)):
            for f in files:
                if f.endswith((".ts", ".tsx", ".css")) and os.path.getmtime(os.path.join(root, f)) > oldest:
                    return True
    return False


def extra_files(repo: str, pairs: list[tuple[str, str]]) -> list[str]:
    """Files in the add-on's kit folders the kit no longer has."""
    wanted = {os.path.normpath(d) for _s, d in pairs}
    out = []
    for folder in kit_dirs(repo):
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                p = os.path.normpath(os.path.join(root, f))
                if f != "README.md" and not f.endswith(".pyc") and f != ".DS_Store" and p not in wanted:
                    out.append(p)
    return out


def check(repo: str) -> list[str]:
    pairs = plan(repo)
    problems = [
        os.path.relpath(d, repo)
        for s, d in pairs
        if not os.path.exists(d) or not filecmp.cmp(s, d, shallow=False)
    ]
    problems += [os.path.relpath(p, repo) + " (not in the kit)" for p in extra_files(repo, pairs)]
    return problems


def sync(repo: str) -> None:
    pairs = plan(repo)
    for p in extra_files(repo, pairs):
        os.remove(p)
    for s, d in pairs:
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(s, d)
    for folder in kit_dirs(repo):
        with open(os.path.join(folder, "README.md"), "w", encoding="utf-8") as f:
            f.write(NOTE)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repos", nargs="+", help="add-on repos (each with src/manifest.json)")
    ap.add_argument("--check", action="store_true", help="only say whether each copy is current")
    args = ap.parse_args()

    if not args.check and page_is_stale():
        print("The kit's page is older than its sources: run `npm run build` first.", file=sys.stderr)
        return 1
    status = 0
    for repo in args.repos:
        repo = os.path.abspath(repo)
        if not os.path.exists(os.path.join(repo, "src", "manifest.json")):
            print(f"{repo}: no src/manifest.json, so not an add-on repo", file=sys.stderr)
            status = 1
            continue
        name = os.path.basename(repo)
        if args.check:
            problems = check(repo)
            if problems:
                status = 1
                print(f"{name}: the kit differs from anki-addon-kit's:")
                for p in problems:
                    print(f"  {p}")
            else:
                print(f"{name}: kit is current")
        else:
            sync(repo)
            print(f"{name}: kit copied")
    return status


if __name__ == "__main__":
    sys.exit(main())
