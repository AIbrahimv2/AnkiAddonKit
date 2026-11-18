#!/usr/bin/env python3
"""Render assets/signature.svg as assets/signature.png, for the AnkiWeb
listings: GitHub serves .svg files as plain text, so a listing can only
show the signature as a PNG.

    python3 tools/signature_png.py

The strokes follow the text colour in the add-ons; here they're the grey
with the same contrast on a light page and a dark one, and the red
underline stays red. AnkiWeb is always light, but browsers that darken
pages (an extension, forced dark mode) leave images as they are, and the
page can't tell, so one image has to read on both. 3x, on a transparent background. Needs Chromium
(/Applications/Chromium.app, or set CHROMIUM).
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "assets", "signature.svg")
PNG = os.path.join(ROOT, "assets", "signature.png")
CHROMIUM = os.environ.get("CHROMIUM", "/Applications/Chromium.app/Contents/MacOS/Chromium")
INK = "#7c7c80"  # contrast about 4.2:1 on white and on a darkened page (#181a1b)
SCALE = 3


def main() -> None:
    svg = open(SVG).read()
    w, h = (int(v) for v in re.search(r'width="(\d+)" height="(\d+)"', svg).groups())
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "signature.html")
        with open(page, "w") as f:
            f.write("<!doctype html><style>html,body{margin:0;background:transparent}"
                    f"svg{{display:block;color:{INK}}}</style>{svg}")
        subprocess.run([CHROMIUM, "--headless=new", f"--user-data-dir={tmp}/profile", "--hide-scrollbars",
                        "--default-background-color=00000000", f"--force-device-scale-factor={SCALE}",
                        f"--window-size={w},{h}", f"--screenshot={PNG}", "file://" + page],
                       check=True, capture_output=True)
    print("wrote", os.path.relpath(PNG, ROOT), f"({w * SCALE}x{h * SCALE})")


if __name__ == "__main__":
    main()
