"""Screenshots for the add-ons' READMEs and AnkiWeb listings, all made one way.

Each add-on has a tools/screenshots.py that imports this (from the kit's
checkout next to it: ../anki-addon-kit/screenshots, or ANKI_ADDON_KIT) and
describes its own scenes. They come out alike:

- Anki's own pages: the toolbar, deck list, review screen and bottom bars
  are Anki's markup (copied from the compiled aqt modules) and stylesheets,
  served from the installed Anki.app as Anki serves them, in dark mode.
- AnkiGlass's Liquid Glass on the main window: its CSS, read from
  ../anki-glass/src, on see-through pages, and the glass drawn as the
  wallpaper behind the window, blurred, under its tint. Other windows, like
  an add-on's own, stay solid, as they do with AnkiGlass.
- A macOS window around each, titled or (for AnkiBare) bare, on macOS
  Tahoe's dark wallpaper, cropped to its top left: of six wallpapers in nine
  crops, measured for the contrast of every word against what's behind it,
  that was the best-looking legible one.
- At 2x. Every image of one add-on is the same size, on the same part of
  the wallpaper, with its window centred, so a README or listing can show
  them all at width="100%" and they line up.

capture.mjs takes the pictures, with headless Chromium over the DevTools
protocol. Needs Node and Chromium (/Applications/Chromium.app, or set
CHROMIUM).
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECTS = os.path.dirname(os.path.dirname(HERE))
CAPTURE = os.path.join(HERE, "capture.mjs")
ANKI_WEB = os.environ.get("ANKI_WEB", "/Applications/Anki.app/Contents/Resources/app_packages/_aqt/data/web")
ANKI_GLASS = os.environ.get("ANKI_GLASS", os.path.join(PROJECTS, "anki-glass", "src"))

# --- made-up decks, the same in every add-on's shots -----------------------------------

# (depth, name, children: None, "+" (collapsed) or "-" (open), new, learn, due).
# Under AnkiGlass Anki's zero counts are faint: keep them few.
DECKS = [
    (0, "AnKing Step Deck", "-", 50, 8, 312),
    (1, "Step 1", "+", 40, 6, 254),
    (1, "Step 2", "+", 10, 2, 58),
    (0, "Lectures", "-", 40, 6, 78),
    (1, "Cardio", None, 30, 4, 57),
    (1, "Renal", None, 10, 2, 21),
    (0, "Pathoma", None, 0, 0, 14),
    (0, "Sketchy Micro", None, 20, 3, 36),
]
CURRENT_DECK = "AnKing Step Deck"
STUDIED = "Studied 186 cards in 31 minutes today (10.0s/card)."

# A card under review: the answer side of a cloze, as an AnKing-style note
# type shows it in dark mode.
CARD_CSS = """
.card { font-family: arial; font-size: 22px; line-height: 1.5; text-align: center; color: black;
        background-color: white; }
.nightMode .card, .night_mode .card { color: #fcfcfc; background-color: #2c2c2c; }
.cloze { font-weight: bold; color: blue; }
.nightMode .cloze, .night_mode .cloze { color: #8fb8ff; }
.extra { margin-top: 1.2em; font-size: 18px; opacity: .8; }
"""
CARD = (
    "Classic galactosemia is caused by a deficiency of "
    "<span class=cloze>galactose&#8209;1&#8209;phosphate uridyltransferase</span>."  # non-breaking hyphens
    "<div class=extra>Jaundice, hepatomegaly and cataracts once milk feeds start. "
    "Treated by taking galactose and lactose out of the diet.</div>"
)
# (label, interval) for Again, Hard, Good and Easy.
ANSWERS = [("Again", "10m"), ("Hard", "2d"), ("Good", "4d"), ("Easy", "9d")]

# --- Anki's pages -------------------------------------------------------------------------

# What AnkiWebView.stdHtml puts on every page on a Mac, and the body classes
# it gives them in dark mode.
STANDARD_CSS = """
body { zoom: 1; background-color: var(--canvas); }
html { font-family:"Helvetica"; }
button {
    --canvas: #fff;
    -webkit-appearance: none;
    background: var(--canvas);
    border-radius: var(--border-radius);
    padding: 3px 12px;
    border: 1px solid var(--border);
    box-shadow: 0px 1px 3px var(--border-subtle);
    font-family: Helvetica
}
.night-mode button { --canvas: #606060; --fg: #eee; }
"""
BODY_CLASS = "isMac nightMode night_mode fancy"


def anki_page(body: str, *css: str, extra: str = "", body_class: str = BODY_CLASS) -> str:
    """A page as stdHtml makes it; `extra` is what add-ons add to its head."""
    links = "".join(f'<link rel="stylesheet" href="/_anki/css/{c}">' for c in ("webview.css", *css))
    extra = f"<style>{extra}</style>" if extra else ""
    return (
        '<!doctype html><html class="night-mode"><head><meta charset="utf-8">'
        f"<style>{STANDARD_CSS}</style>{links}{extra}</head>"
        f'<body class="{body_class}">{body}</body></html>'
    )


def toolbar(glass: dict | None) -> str:
    """The top bar: Decks, Add, Browse, Stats, Sync."""
    links = [("decks", "Decks", "D"), ("add", "Add", "A"), ("browse", "Browse", "B"), ("stats", "Stats", "T"),
             ("sync", "Sync", "Y")]
    items = "".join(
        f'<a class=hitem tabindex="-1" aria-label="Shortcut key: {k}" title="Shortcut key: {k}" id="{i}" href=# '
        f"onclick=\"return pycmd('{i}')\">{label}"
        + ("<img id=sync-spinner src='/_anki/imgs/refresh.svg'>" if i == "sync" else "") + "</a>"
        for i, label, k in links)
    return anki_page(
        '<div class="header"><div class="left-tray"></div>'
        f'<div class="toolbar">{items}</div><div class="right-tray"></div></div>', "toolbar.css",
        extra=glass["toolbar"] if glass else "")


def deck_browser(glass: dict | None, decks: list = DECKS, current: str = CURRENT_DECK,
                 studied: str = STUDIED, stats: str = "") -> str:
    """The deck list. `stats` is what add-ons append to its stats area (the
    deck_browser_will_render_content hook), after the "Studied" line."""
    rows = [
        "<tr><th colspan=5 align=start>Deck</th><th class=count>New</th><th class=count>Learn</th>"
        "<th class=count>Due</th><th class=optscol></th></tr>",
        "<tr class='top-level-drag-row'><td colspan='6'>&nbsp;</td></tr>",
    ]

    def count(n, kind):
        return f'<td align=end><span class="{kind if n else "zero-count"}">{n}</span></td>'

    for did, (depth, name, children, new, learn, due) in enumerate(decks, start=1):
        klass = "deck current" if name == current else "deck"
        collapse = (f"<a class=collapse href=# onclick='return pycmd(\"collapse:{did}\")'>{children}</a>"
                    if children else "<span class=collapse></span>")
        rows.append(
            f"<tr class='{klass}' id='{did}'><td class=decktd colspan=5>{'&nbsp;' * 6 * depth}{collapse}"
            f"<a class=\"deck \" href=# onclick=\"return pycmd('open:{did}')\">{name}</a></td>"
            f"{count(new, 'new-count')}{count(learn, 'learn-count')}{count(due, 'review-count')}"
            f"<td align=center class=opts><a><img src='/_anki/imgs/gears.svg' class=gears></a></td></tr>")
    stats = f'<div id="studiedToday"><span>{studied}</span></div>' + stats
    body = f"<center>\n<table cellspacing=0 cellpadding=3>{''.join(rows)}</table>\n<br>\n{stats}</center>"
    return anki_page(body, "deckbrowser.css", extra=glass["deck"] if glass else "")


def deck_browser_bar(glass: dict | None) -> str:
    """The deck list's bottom bar. Anki loads toolbar.css there too, which
    takes webview.css's 2em body margin away."""
    buttons = "".join(f"<button onclick='pycmd(\"{c}\");'>{label}</button>"
                      for c, label in (("shared", "Get Shared"), ("add", "Create Deck"), ("import", "Import File")))
    return anki_page(f"<center id=outer><table width=100% id=header><tr><td align=center>\n{buttons}</td></tr>"
                     "</table></center>", "toolbar.css", "toolbar-bottom.css", extra=glass["bottom"] if glass else "")


def reviewer(glass: dict | None, card: str = CARD, css: str = CARD_CSS) -> str:
    """A card's answer side, as the reviewer shows it."""
    body = ('<div id="_mark" hidden>&#x2605;</div><div id="_flag" hidden>&#x2691;</div>'
            f'<div id="qa" dir="auto"><style>{css}</style>{card}</div>')
    return anki_page(body, "reviewer.css", extra=glass["review"] if glass else "",
                     body_class=BODY_CLASS + " card card1")


def reviewer_bar(glass: dict | None, answers: list = ANSWERS) -> str:
    """The reviewer's bottom bar with the answer buttons and their intervals."""
    def button(i, label, interval):
        default = 'id="defease" ' if label == "Good" else ""
        return (f'<td align=center><button {default}title="Shortcut key: {i}" data-ease="{i}" '
                f"onclick='pycmd(\"ease{i}\");'><span class=\"nobold\">{interval}</span>{label}</button></td>")

    buttons = "".join(button(i, label, interval) for i, (label, interval) in enumerate(answers, start=1))
    body = (
        "<center id=outer>\n<table id=innertable width=100% cellspacing=0 cellpadding=0>\n<tr>\n"
        "<td align=start valign=top class=stat>\n"
        "<button title=\"Shortcut key: E\" onclick=\"pycmd('edit');\">Edit</button></td>\n"
        "<td align=center valign=top id=middle>\n"
        f"<center><table cellpadding=0 cellspacing=0><tr>{buttons}</tr></table></center>\n</td>\n"
        "<td align=end valign=top class=stat>\n"
        "<button title=\"Shortcut key: M\" onclick=\"pycmd('more');\">More &#x25BE;"
        "<span id=time class=stattxt></span></button>\n</td>\n</tr>\n</table>\n</center>"
    )
    return anki_page(body, "toolbar-bottom.css", "reviewer-bottom.css", extra=glass["bottom"] if glass else "")


# Anki's three web views, one above the other, each sized to fit as Anki does.
# Under AnkiGlass they're see-through, so the page is left clear for the glass;
# its colour-scheme matches theirs, or Chromium paints the frames opaque.
MAIN_WINDOW = """<!doctype html><html><head><style>
:root { color-scheme: dark; }
html, body { margin: 0; height: 100%; background: BACKGROUND; }
body { display: flex; flex-direction: column; }
iframe { display: block; border: 0; width: 100%; flex: none; }
#main { flex: 1; }
</style></head><body>
<iframe id="top" src="PREFIX-top.html"></iframe><iframe id="main" src="PREFIX-main.html"></iframe>
<iframe id="bottom" src="PREFIX-bottom.html"></iframe>
<script>
window.shotReady = new Promise((resolve) => window.addEventListener('load', () => {
  for (const id of ['top', 'bottom']) {
    const f = document.getElementById(id), body = f.contentDocument.body;
    f.style.height = Math.max(body.scrollHeight, body.getBoundingClientRect().height
      + parseFloat(getComputedStyle(body).marginBottom)) + 'px';
  }
  resolve(true);
}));
</script></body></html>"""

# --- AnkiGlass -----------------------------------------------------------------------------


def load_glass(src: str = ANKI_GLASS) -> dict:
    """AnkiGlass's CSS for each of the main window's pages, and its dark tint,
    read from its source (it can't be imported outside Anki): what its
    webview_will_set_content hook adds to each page in dark mode."""
    path = os.path.join(src, "__init__.py")
    if not os.path.isfile(path):
        raise SystemExit(f"AnkiGlass isn't at {src}: set ANKI_GLASS, or pass --plain")
    found = {}
    for node in ast.parse(open(path).read()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                found[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    tint = found["_DEFAULTS"]["tint_dark"]
    root = f":root{{--lg-tint:{tint}}}\n"  # its tint_css()
    common = found["GLASS_COMMON_CSS"]
    return {
        "tint": tint,
        "toolbar": root + common + found["GLASS_TOP_CSS"],
        "deck": root + found["GLASS_CONTENT_CSS"] + found["GLASS_DECK_CSS"],
        "review": root + found["GLASS_CONTENT_CSS"],
        "bottom": root + common + found["GLASS_BOTTOM_CSS"],
    }


# --- the window, on the wallpaper ----------------------------------------------------------

MAIN_SIZE = (760, 622)  # Anki's main window in the shots: its content, below the title bar
TITLE_BAR = 28
RADIUS = 16
PAD = (52, 64, 76)  # wallpaper around an add-on's largest window: top, sides, bottom
WALLPAPER = "/System/Library/ExtensionKit/Extensions/NeptuneOneWallpaper.appex/Contents/Resources/TahoeDark.heic"
CAPTURED = os.path.join(HERE, "wallpaper.png")  # made by --capture-wallpaper; not in git
SCREEN_WIDTH = 1512  # the wallpaper's width in the shots: a MacBook Pro 14"'s screen, in points
# Which part of it shows (CSS background-position). Anki's coloured counts
# suffer most over a bright patch of wallpaper, so check them after changing it.
WALLPAPER_POSITION = "0% 0%"


def outer(frame: dict) -> tuple:
    w, h = frame["size"]
    return w, h + (0 if frame.get("bare") else TITLE_BAR)


def stage_for(frames: list) -> tuple:
    """One size for all of an add-on's images: its largest window, with the
    wallpaper around it."""
    return (max(outer(f)[0] for f in frames) + 2 * PAD[1],
            max(outer(f)[1] for f in frames) + PAD[0] + PAD[2])


def window(frame: dict, stage: tuple, wallpaper: tuple) -> str:
    """A macOS window holding frame["image"] (the window's content, frame["size"]
    in points), with frame["title"], on the wallpaper. With a "tint" it's
    AnkiGlass's: the glass is the wallpaper behind it, blurred, under that
    tint, its title bar see-through. "bare" leaves the title bar out, as
    AnkiBare does: its space goes to the content."""
    w, h = frame["size"]
    ow, oh = outer(frame)
    stage_w, stage_h = stage
    # The window centred across, and down in the same proportion as the
    # largest one (its shadow falls below).
    left = (stage_w - ow) / 2
    top = (stage_h - oh) * PAD[0] / (PAD[0] + PAD[2])
    name, ww, wh = wallpaper
    scale = max(SCREEN_WIDTH / ww, stage_w / ww, stage_h / wh)
    backdrop = f"#1a1a2e url('{name}') {WALLPAPER_POSITION} / {ww * scale:.0f}px {wh * scale:.0f}px no-repeat"
    if frame.get("tint"):
        win = f"background: {frame['tint']}; backdrop-filter: blur(28px) saturate(150%);"
        rim, bar = "rgba(255,255,255,.2)", "background: transparent;"
    else:
        win = "background: #2c2c2c;"
        rim, bar = "rgba(255,255,255,.11)", "background: #353535; box-shadow: inset 0 -1px 0 rgba(0,0,0,.55);"
    title_bar = "" if frame.get("bare") else (
        '<div class="bar"><span class="lights"><i style="background:#ff5f57"></i>'
        f'<i style="background:#febc2e"></i><i style="background:#28c840"></i></span>{frame["title"]}</div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html, body {{ margin: 0; height: 100%; }}
body {{ background: {backdrop}; }}
.win {{ position: absolute; left: {left:g}px; top: {top:g}px; width: {w}px; border-radius: {RADIUS}px;
        overflow: hidden; {win}
        box-shadow: 0 0 0 .5px rgba(0,0,0,.7), 0 24px 60px rgba(0,0,0,.45), 0 6px 18px rgba(0,0,0,.25); }}
.win::after {{ content: ""; position: absolute; inset: 0; border-radius: {RADIUS}px; pointer-events: none;
               box-shadow: inset 0 0 0 1px {rim}; }}
.bar {{ position: relative; height: {TITLE_BAR}px; display: flex; align-items: center; justify-content: center;
        {bar} font: 600 13px -apple-system, system-ui, sans-serif; color: rgba(255,255,255,.85); }}
.lights {{ position: absolute; left: 13px; top: 8px; display: flex; gap: 8px; }}
.lights i {{ width: 12px; height: 12px; border-radius: 50%; box-shadow: inset 0 0 0 .5px rgba(0,0,0,.25); }}
img {{ display: block; width: {w}px; height: {h}px; }}
</style></head><body><div class="win">{title_bar}<img src="{frame["image"]}"></div></body></html>"""


def add_wallpaper_args(ap) -> None:
    which = ap.add_mutually_exclusive_group()
    which.add_argument("--capture-wallpaper", action="store_true",
                       help="use the desktop's wallpaper as it shows now (saved to the kit's screenshots/wallpaper.png)")
    which.add_argument("--wallpaper", default=WALLPAPER, help="an image, or a video to take the first frame of")


def capture_wallpaper(out: str = CAPTURED) -> None:
    """The desktop's wallpaper as it shows now, without the windows and icons
    on it: macOS draws it in a window of its own, which screencapture can
    take alone. For wallpapers macOS draws live (Sequoia's, say), which have
    no file. Needs this app to be allowed to record the screen."""
    find = ('ObjC.import("CoreGraphics");'
            "const all = ObjC.deepUnwrap(ObjC.castRefToObject("
            "$.CGWindowListCopyWindowInfo($.kCGWindowListOptionAll, 0)));"
            'const w = all.find((w) => w.kCGWindowName === "Wallpaper" && w.kCGWindowLayer < -1000'
            " && w.kCGWindowBounds.X === 0 && w.kCGWindowBounds.Y === 0);"  # the main display's
            'w ? String(w.kCGWindowNumber) : ""')
    wid = subprocess.run(["osascript", "-l", "JavaScript", "-e", find], capture_output=True, text=True).stdout.strip()
    if not wid:
        raise SystemExit("couldn't find the desktop's wallpaper: allow this app to record the screen "
                         "(System Settings > Privacy & Security > Screen & System Audio Recording)")
    subprocess.run(["screencapture", "-x", "-o", "-l", wid, out], check=True)
    print("captured the wallpaper to", out)


def prepare_wallpaper(path: str, work: str) -> tuple:
    """The wallpaper as a PNG in `work`, and its size. macOS keeps its stills
    as HEIC, which Chromium can't show, and some only as videos."""
    if not os.path.isfile(path):
        if path == WALLPAPER:
            raise SystemExit("Tahoe's wallpaper isn't here (it needs macOS 26 or later): "
                             "pass --wallpaper or --capture-wallpaper")
        raise SystemExit(f"no wallpaper at {path}")
    out = os.path.join(work, "wallpaper.png")
    if path.lower().endswith((".mov", ".mp4", ".m4v")):
        # Quick Look's thumbnail of a video is its first frame.
        subprocess.run(["qlmanage", "-t", "-s", "3840", "-o", work, path], check=True, capture_output=True)
        os.replace(os.path.join(work, os.path.basename(path) + ".png"), out)
    else:
        subprocess.run(["sips", "-s", "format", "png", path, "--out", out], check=True, capture_output=True)
    sizes = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", out],
                           check=True, capture_output=True, text=True).stdout.split()
    return "wallpaper.png", int(sizes[-3]), int(sizes[-1])


# --- real cards ---------------------------------------------------------------------------

DEFAULT_COLLECTION = os.path.expanduser("~/Library/Application Support/Anki2/Default/collection.anki2")


def anki_python() -> str:
    """Anki's own Python (ANKI_PYTHON, or the launcher's), which can import anki."""
    import glob

    found = os.environ.get("ANKI_PYTHON") or "".join(sorted(glob.glob(os.path.expanduser(
        "~/Library/Application Support/AnkiProgramFiles/python/*/bin/python3")))[-1:])
    if not found:
        raise SystemExit("Anki's Python wasn't found: set ANKI_PYTHON")
    return found


def export_cards(collection: str, nids: list, out: str) -> dict:
    """Real notes' cards, rendered by Anki from one copy of the collection
    (card.py), into `out` with their media; each one's HTML, for reviewer()."""
    if not os.path.isfile(collection):
        raise SystemExit(f"no collection at {collection}: pass --collection")
    subprocess.run([anki_python(), os.path.join(HERE, "card.py"), collection, out, *map(str, nids)],
                   check=True, capture_output=True)
    cards = {}
    for nid in nids:
        with open(os.path.join(out, f"card-{nid}.html")) as f:
            cards[nid] = f.read()
    return cards


def export_card(collection: str, nid: int, out: str) -> str:
    return export_cards(collection, [nid], out)[nid]


# --- running it --------------------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(url: str, timeout: float = 30) -> None:
    t = time.time()
    while time.time() - t < timeout:
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return
        except OSError:
            time.sleep(0.2)
    raise SystemExit(f"{url} didn't answer")


class Session:
    """A temporary folder, served over HTTP with Anki's own files under
    /_anki/ as Anki serves them, where the pages are written and shot.

        with shots.Session() as s:
            main = s.main_window("deck", shots.toolbar(glass), ..., glass)
            s.capture([{"url": main, ..., "out": "deck.png"}])
            s.frames([{"image": "deck.png", ...}], wallpaper, out_dir)
    """

    def __init__(self):
        self.work = tempfile.mkdtemp(prefix="addon-shots-")
        work = self.work

        class Handler(SimpleHTTPRequestHandler):
            def translate_path(self, path):
                if path.startswith("/_anki/"):
                    return os.path.join(ANKI_WEB, path[len("/_anki/"):].split("?")[0])
                return super().translate_path(path)

            def log_message(self, *a):
                pass

        if not os.path.isdir(ANKI_WEB):
            raise SystemExit(f"Anki's web files aren't at {ANKI_WEB}: set ANKI_WEB")
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=work))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.srv.shutdown()
        shutil.rmtree(self.work, ignore_errors=True)

    def path(self, name: str) -> str:
        return os.path.join(self.work, name)

    def write(self, name: str, html: str) -> str:
        with open(self.path(name), "w") as f:
            f.write(html)
        return f"{self.base}/{name}"

    def main_window(self, prefix: str, top: str, main: str, bottom: str, glass: dict | None) -> str:
        """Anki's main window with these three pages; its URL, for a shot with
        setup "window.shotReady" (and "transparent" under AnkiGlass)."""
        for part, html in (("top", top), ("main", main), ("bottom", bottom)):
            self.write(f"{prefix}-{part}.html", html)
        page = MAIN_WINDOW.replace("PREFIX", prefix).replace("BACKGROUND", "transparent" if glass else "#2c2c2c")
        return self.write(f"{prefix}.html", page)

    def capture(self, shots: list) -> None:
        """Shots for capture.mjs; a relative "out" or "result" is in the folder."""
        for s in shots:
            for key in ("out", "result"):
                if key in s and not os.path.isabs(s[key]):
                    s[key] = self.path(s[key])
        with open(self.path("shots.json"), "w") as f:
            json.dump(shots, f)
        subprocess.run(["node", CAPTURE, self.path("shots.json")], check=True)

    def frames(self, frames: list, wallpaper: tuple, out_dir: str) -> list:
        """Each frame's window on the wallpaper, all one size, into out_dir.
        A frame: "image" (in the folder), "size", "title", "out" (a file name),
        and "tint" for AnkiGlass's glass, "bare" for no title bar."""
        stage = stage_for(frames)
        os.makedirs(out_dir, exist_ok=True)
        shots = []
        for i, f in enumerate(frames):
            url = self.write(f"frame-{i}.html", window(f, stage, wallpaper))
            shots.append({"url": url, "width": stage[0], "height": stage[1], "wait": 300,
                          "out": os.path.join(out_dir, f["out"])})
        self.capture(shots)
        return [s["out"] for s in shots]


def wallpaper_for(args, session: Session) -> tuple:
    """The wallpaper the options name, ready in the session's folder."""
    path = args.wallpaper
    if args.capture_wallpaper:
        capture_wallpaper(CAPTURED)
        path = CAPTURED
    return prepare_wallpaper(path, session.work)
