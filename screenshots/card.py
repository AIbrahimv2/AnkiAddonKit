"""Render real cards' answer sides, as Anki would show them, for review shots.

    <Anki's Python> card.py COLLECTION OUT_DIR NOTE_ID [NOTE_ID ...]

Copies the collection (with its -wal and -shm, so a collection Anki has
open copies whole) to a temporary folder, opens the copy, and writes to
OUT_DIR, for each note, card-<NOTE_ID>.html: its first card's answer with
its note type's CSS. The media files they use (images, and fonts the CSS
loads) are copied there too, from the collection.media folder next to the
collection. The collection itself is never opened. shots.export_card and
shots.export_cards run this with Anki's own Python.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile


def main() -> None:
    collection, out, nids = sys.argv[1], sys.argv[2], [int(n) for n in sys.argv[3:]]
    media = os.path.join(os.path.dirname(collection), "collection.media")
    if importlib.util.find_spec("anki") is None:  # the launcher's Python finds it in the app
        sys.path.insert(0, "/Applications/Anki.app/Contents/Resources/app_packages")
    from anki.collection import Collection

    rendered = {}
    with tempfile.TemporaryDirectory() as tmp:
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(collection + suffix):
                shutil.copy2(collection + suffix, os.path.join(tmp, "collection.anki2" + suffix))
        col = Collection(os.path.join(tmp, "collection.anki2"))
        try:
            for nid in nids:
                # The answer with the note type's CSS, as the reviewer gets it.
                rendered[nid] = col.get_note(nid).cards()[0].answer()
        finally:
            col.close()
    os.makedirs(out, exist_ok=True)
    copied = set()
    for nid, html in rendered.items():
        with open(os.path.join(out, f"card-{nid}.html"), "w") as f:
            f.write(html)
        names = set(re.findall(r'<img[^>]+src="([^"/]+)"', html)) | set(
            re.findall(r"url\(['\"]?([^'\")/]+)['\"]?\)", html))
        for name in names - copied:
            src = os.path.join(media, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(out, name))
                copied.add(name)
    print(json.dumps({"cards": [f"card-{n}.html" for n in rendered], "media": sorted(copied)}))


if __name__ == "__main__":
    main()
