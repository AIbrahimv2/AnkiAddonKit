#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Answer the kit page's bridge calls outside Anki, for `npm run dev`.

Runs the real kit code (py/) with the add-ons' real changelogs from the
sibling repos, and makes up the rest: which add-ons are installed, which
versions you've seen, and what AnkiWeb says.

    python3 tools/preview.py                     # everything installed
    python3 tools/preview.py --missing glass,bare  # show Install buttons
    python3 tools/preview.py --seen exam-timeline=1.0.0 --update stepwise

then `npm run dev` and open http://localhost:5184/?id=glass&tab=settings
(add &theme=dark for dark mode).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = os.path.dirname(KIT)

# The kit's Python, as the package "kit" (what an add-on calls src/kit/).
spec = importlib.util.spec_from_file_location("kit", os.path.join(KIT, "py", "__init__.py"),
                                              submodule_search_locations=[os.path.join(KIT, "py")])
kit = importlib.util.module_from_spec(spec)
sys.modules["kit"] = kit
spec.loader.exec_module(kit)
from kit import family  # noqa: E402

# Each add-on: its repo's src/, and its folder name in addons21 (a number
# for an AnkiWeb install, so it isn't shown as your own copy).
ADDONS = {
    "stepwise": ("anki-stepwise", "1949793886"),
    "skim": ("anki-skim", "anki-skim"),
    "exam-timeline": ("anki-exam-timeline", "341595498"),
    "glass": ("anki-glass", "anki_glass"),
    "bare": ("anki-bare", "1505882046"),
}


def glass_schema():
    path = os.path.join(PROJECTS, "anki-glass", "src", "settings_schema.py")
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location("glass_schema", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def glass_settings(mod):
    """AnkiGlass's schema, as with a log on, and a stand-in for its button."""
    if not hasattr(mod, "schema"):
        return mod.SCHEMA, {}
    return mod.schema(True), {"show_log": lambda: "(the log opens in a window inside Anki)"}


def setup(args) -> None:
    reg = family.registry()
    missing = set(filter(None, args.missing.split(",")))
    schema = glass_schema()
    glass, glass_actions = glass_settings(schema) if schema else (None, {})
    for addon_id, (repo, dir_name) in ADDONS.items():
        if addon_id in missing:
            continue
        reg["members"][addon_id] = {
            "id": addon_id,
            "dir": dir_name,
            "path": os.path.join(PROJECTS, repo, "src"),
            "kit": family.KIT_VERSION,
            "open_settings": (lambda a=addon_id: print("open settings of", a))
            if addon_id in ("stepwise", "skim") else None,
            "schema": glass if addon_id == "glass" else None,
            "note": schema.NOTE if (addon_id == "glass" and schema) else None,
            "actions": glass_actions if addon_id == "glass" else {},
            "open_page": None,
        }
        # Seen: the latest version, unless --seen says older.
        version = family.changelog.latest_version(family.releases(os.path.join(PROJECTS, repo, "src")))
        family.set_kit_state(dir_name, seen=version, notified=version)
    for pair in args.seen:
        addon_id, version = pair.split("=")
        family.set_kit_state(ADDONS[addon_id][1], seen=version, notified=version)
    if schema:
        from kit import settings
        settings._outside["anki_glass"] = dict(schema.PREVIEW_CONFIG)
        settings._outside_defaults["anki_glass"] = dict(schema.PREVIEW_CONFIG)

    def fake_updates():
        out = {}
        for a in family._addons(with_changes=False):
            if a["installed"]:
                out[a["id"]] = "dev" if a["dev"] else ("available" if a["id"] in args.update else "current")
        return {"done": True, "updates": out}

    family.updates = fake_updates
    family._self["id"] = args.self


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        msg = json.loads(body)
        if msg.get("cmd") != "kit":
            reply = {"error": f"Unknown command: {msg.get('cmd')}"}
        elif msg.get("op") in ("install", "page", "close"):
            print(msg)
            reply = {}
        else:
            reply = family.command(msg)
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=5185)
    p.add_argument("--self", default="glass", help="the add-on a call without an id is about")
    p.add_argument("--missing", default="", help="add-ons to show as not installed, comma-separated")
    p.add_argument("--seen", action="append", default=[], help="id=version you last saw, to show it as new")
    p.add_argument("--update", action="append", default=[], help="an add-on AnkiWeb has an update for")
    args = p.parse_args()
    setup(args)
    print(f"kit preview bridge on http://127.0.0.1:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
