# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""The kit's Python, outside Anki: python3 -m unittest discover tests"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = os.path.dirname(KIT)

spec = importlib.util.spec_from_file_location(
    "kit", os.path.join(KIT, "py", "__init__.py"), submodule_search_locations=[os.path.join(KIT, "py")]
)
kit = importlib.util.module_from_spec(spec)
sys.modules["kit"] = kit
spec.loader.exec_module(kit)
from kit import changelog, family, settings  # noqa: E402

SAMPLE = """# Changelog

All notable changes...

## [Unreleased]

### Added

- **Bold thing**, with `code` and a
  [link](https://example.com) that runs on.
  - a nested point

## [1.10.0] - 2026-11-09

### Fixed

- One fix.

## 1.9.2 - 2026-10-01
- Bullet straight under the version.

## 1.0.0
- Initial release.
"""


class ChangelogTest(unittest.TestCase):
    def test_parse(self):
        rel = changelog.parse(SAMPLE)
        self.assertEqual([r["version"] for r in rel], [None, "1.10.0", "1.9.2", "1.0.0"])
        self.assertEqual(rel[1]["date"], "2026-11-09")
        self.assertIsNone(rel[3]["date"])
        item = rel[0]["sections"][0]["items"][0]
        self.assertEqual(
            item,
            "**Bold thing**, with `code` and a [link](https://example.com) that runs on. a nested point",
        )
        self.assertEqual(rel[2]["sections"], [{"title": "", "items": ["Bullet straight under the version."]}])
        self.assertEqual(changelog.latest_version(rel), "1.10.0")

    def test_versions(self):
        self.assertTrue(changelog.newer("1.10.0", "1.9.2"))
        self.assertTrue(changelog.newer("1.0.1", "1.0.0"))
        self.assertFalse(changelog.newer("1.0.0", "1.0.0"))
        self.assertFalse(changelog.newer(None, "1.0.0"))
        self.assertTrue(changelog.newer("1.0.0", None))

    def test_real_changelogs(self):
        """Every add-on's changelog parses, with a version or Unreleased."""
        for repo in ("anki-tag-queue", "anki-skim", "anki-exam-timeline", "anki-glass", "anki-bare"):
            path = os.path.join(PROJECTS, repo, "CHANGELOG.md")
            if not os.path.exists(path):
                continue
            with self.subTest(repo=repo):
                with open(path, encoding="utf-8") as f:
                    rel = changelog.parse(f.read())
                self.assertTrue(rel)
                for r in rel:
                    for s in r["sections"]:
                        for item in s["items"]:
                            self.assertTrue(item and not item.startswith("- "), item)


class FamilyTest(unittest.TestCase):
    def setUp(self):
        family._outside.update(registry=None, meta={})
        family._self["id"] = None
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def member(self, addon_id, dir_name, log, **extra):
        path = os.path.join(self.tmp.name, dir_name)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "CHANGELOG.md"), "w") as f:
            f.write(log)
        family.registry()["members"][addon_id] = {
            "id": addon_id, "dir": dir_name, "path": path, "kit": 1,
            "open_settings": None, "schema": None, "note": None, "open_page": None, **extra,
        }

    def test_catalog(self):
        ids = [a["id"] for a in family.catalog()["addons"]]
        self.assertEqual(ids, ["stepwise", "skim", "exam-timeline", "glass", "bare"])

    def test_unseen_and_notice(self):
        self.member("stepwise", "1949793886", "## [1.2.0] - 2026-11-20\n- New.\n## [1.1.0]\n- Old.\n")
        self.member("exam-timeline", "anki-exam-timeline", "## [1.1.0]\n- Same.\n")
        family.set_kit_state("1949793886", seen="1.1.0", notified="1.1.0")
        family.set_kit_state("anki-exam-timeline", seen="1.1.0", notified="1.1.0")

        about = {a["id"]: a for a in family.about("stepwise")["addons"]}
        self.assertTrue(about["stepwise"]["unseen"])
        self.assertEqual([r["isNew"] for r in about["stepwise"]["changes"]], [True, False])
        self.assertFalse(about["exam-timeline"]["unseen"])
        self.assertTrue(about["exam-timeline"]["dev"])
        self.assertFalse(about["stepwise"]["dev"])
        self.assertFalse(about["glass"]["installed"])

        # The notice names it once; seeing What's new clears the dot.
        self.assertEqual([a["id"] for a in family.updated_unnoticed()], ["stepwise"])
        family.mark_notified(family.updated_unnoticed())
        self.assertEqual(family.updated_unnoticed(), [])
        self.assertTrue(family.about()["addons"][0]["unseen"])
        family.command({"cmd": "kit", "op": "seen", "id": "stepwise"})
        self.assertFalse(family.about()["addons"][0]["unseen"])

    def test_first_run_is_not_an_update(self):
        family._first_run("kit")  # this checkout's own folder: no changelog
        self.assertIn("seen", family.kit_state(family.ADDON))

    def test_commands_never_raise(self):
        self.assertIn("error", family.command({"op": "nope"}))
        self.assertIn("error", family.command({"op": "open", "url": "file:///etc/passwd"}))
        self.assertIn("error", family.command({"op": "install", "id": "skim"}))  # not on AnkiWeb

    def test_updates_outside_anki(self):
        self.member("glass", "anki_glass", "## 1.1.0\n- x\n")
        self.member("bare", "1505882046", "## [1.0.0]\n- x\n")
        family._updates.update(state="idle", at=0.0, result={})
        r = family.updates()
        self.assertEqual(r, {"done": True, "updates": {"glass": "dev", "bare": "unknown"}})


class SettingsTest(unittest.TestCase):
    SCHEMA = [{"section": "S", "fields": [
        {"key": "on", "type": "switch", "label": "On"},
        {"key": "screens", "type": "multi", "label": "Screens",
         "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]},
        {"key": "side", "type": "choice", "label": "Side",
         "options": [{"value": "front", "label": "Front"}, {"value": "back", "label": "Back"}]},
        {"key": "tint", "type": "text", "label": "Tint"},
    ]}]

    def test_check(self):
        clean, problems = settings.check(self.SCHEMA, {
            "on": 1, "screens": ["b", "zzz", "a"], "side": "front", "tint": "  red  ",
        })
        self.assertEqual(clean, {"on": True, "screens": ["a", "b"], "side": "front", "tint": "red"})
        self.assertEqual(problems, {})
        _clean, problems = settings.check(self.SCHEMA, {"side": "up", "tint": "", "screens": "a"})
        self.assertEqual(set(problems), {"side", "tint", "screens"})

    def test_save_round_trip(self):
        family._outside.update(registry=None, meta={})
        family.registry()["members"]["glass"] = {"id": "glass", "dir": "anki_glass", "schema": self.SCHEMA, "note": "Restart."}
        settings._outside["anki_glass"] = {"on": False, "other": 1}
        r = family.command({"op": "save_settings", "id": "glass", "values": {"on": True, "tint": "blue"}})
        self.assertEqual(r, {"saved": True, "note": "Restart."})
        self.assertEqual(settings._outside["anki_glass"], {"on": True, "other": 1, "tint": "blue"})
        loaded = family.command({"op": "settings", "id": "glass"})
        self.assertEqual(loaded["values"]["on"], True)

    def test_actions_and_a_schema_that_follows_state(self):
        family._outside.update(registry=None, meta={})
        state = {"off": False}

        def schema():
            row = {"key": "off_now", "type": "action", "label": "For now"}
            if not state["off"]:
                row["button"] = "Turn off"
            return self.SCHEMA + [{"section": "Turn off", "fields": [row]}]

        def off_now():
            state["off"] = True
            return "Turned off."

        family.registry()["members"]["glass"] = {
            "id": "glass", "dir": "anki_glass", "schema": schema, "note": None, "actions": {"off_now": off_now},
        }
        settings._outside["anki_glass"] = {"on": True}
        loaded = family.command({"op": "settings", "id": "glass"})
        self.assertNotIn("off_now", loaded["values"])  # a button, not a value
        self.assertEqual(loaded["schema"][-1]["fields"][0]["button"], "Turn off")
        self.assertEqual(family.command({"op": "action", "id": "glass", "key": "off_now"}), {"message": "Turned off."})
        loaded = family.command({"op": "settings", "id": "glass"})
        self.assertNotIn("button", loaded["schema"][-1]["fields"][0])
        self.assertIn("error", family.command({"op": "action", "id": "glass", "key": "nope"}))
        # Saving ignores the action rows.
        self.assertEqual(family.command({"op": "save_settings", "id": "glass", "values": {"on": False}})["saved"], True)


if __name__ == "__main__":
    unittest.main()
