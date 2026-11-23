#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Screenshots of the kit's own window (Settings, What's new, About), made
the way shots.py makes the add-ons' others.

    python3 screenshots/kit_window.py [--addon glass] [--out DIR] [--plain] [wallpaper options]

The window is the built page (py/web/page.js and page.css, as page.py loads
it in Anki), dark, in a macOS window on Tahoe's wallpaper, with AnkiGlass's
glass behind it unless --plain. What the page asks for is answered as
tools/preview.py answers it: the kit's real Python and the add-ons' real
changelogs from the sibling repos, with the rest made up (all installed,
everything seen, nothing to update). No collection is read.

Writes into DIR (default: kit-window/ in the current folder):
settings.png, news.png (scrolled partway, to show the content fading under
the tabs) and about.png. Needs macOS, as shots.py does.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import threading
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import shots  # noqa: E402

# The kit window's size in Anki (page.py's KitWindow): its content, below the title bar.
SIZE = (880, 740)


def load_preview():
    spec = importlib.util.spec_from_file_location("kit_preview", os.path.join(KIT, "tools", "preview.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def start_bridge(preview, addon: str) -> int:
    """tools/preview.py's answers on a free port, open to the shots' pages
    (another origin)."""
    opts = argparse.Namespace(missing="", seen=[], update=[])
    setattr(opts, "self", addon)  # a keyword Namespace() won't take
    preview.setup(opts)

    class Handler(preview.Handler):
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def page(addon: str, tab: str, bridge: int) -> str:
    """The page as page.py's _load() makes it, with pycmd() going to the bridge."""
    boot = json.dumps({"id": addon, "tab": tab, "hosted": None})
    pycmd = (
        "window.pycmd = (arg, cb) => fetch('http://127.0.0.1:%d/', {method: 'POST', body: arg})"
        ".then((r) => r.json()).then((reply) => cb && cb(reply));" % bridge
    )
    body = (f'<div id="root"></div><script>{pycmd}window.KIT_PAGE = {boot};</script>'
            '<script src="page.js"></script>')
    return shots.anki_page(body, extra=open(os.path.join(KIT, "py", "web", "page.css")).read())


# Wait for the tab's content, then scroll what scrolls (the content area, or
# Settings' rows) by SCROLL px.
SETUP = """(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  for (let i = 0; i < 200 && !document.querySelector(%s); i++) await sleep(50);
  if (!document.querySelector(%s)) throw new Error('the tab did not render');
  await sleep(400);
  const el = document.querySelector('.kit-main .settings') || document.querySelector('.kit-main');
  if (el) el.scrollTop = %d;
  return true;
})()"""

TABS = {  # tab: (what shows it's rendered, how far to scroll)
    "settings": (".set-card", 0),
    "news": (".kit-release", 380),
    "about": (".kit-card", 0),
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--addon", default="glass", help="whose window: glass, stepwise, skim, exam-timeline, bare")
    ap.add_argument("--out", default="kit-window", help="folder for the PNGs")
    ap.add_argument("--plain", action="store_true", help="without AnkiGlass's glass")
    shots.add_wallpaper_args(ap)
    args = ap.parse_args()

    glass = None if args.plain else shots.load_glass()
    bridge = start_bridge(load_preview(), args.addon)
    title = {"glass": "AnkiGlass", "stepwise": "Stepwise", "skim": "Skim",
             "exam-timeline": "Exam Timeline", "bare": "AnkiBare"}.get(args.addon, args.addon)
    with shots.Session() as s:
        shutil.copy(os.path.join(KIT, "py", "web", "page.js"), s.path("page.js"))
        captures, frames = [], []
        for tab, (ready, scroll) in TABS.items():
            url = s.write(f"{tab}.html", page(args.addon, tab, bridge))
            sel = json.dumps(ready)
            captures.append({"url": url, "width": SIZE[0], "height": SIZE[1], "wait": 500,
                             "setup": SETUP % (sel, sel, scroll), "out": f"{tab}.png",
                             **({"preload": glass["window"], "transparent": True} if glass else {})})
            frames.append({"image": f"{tab}.png", "size": SIZE, "title": title,
                           "tint": glass and glass["tint"], "out": f"{tab}.png"})
        s.capture(captures)
        out = s.frames(frames, shots.wallpaper_for(args, s), os.path.abspath(args.out))
    for path in out:
        print("wrote", path)


if __name__ == "__main__":
    main()
