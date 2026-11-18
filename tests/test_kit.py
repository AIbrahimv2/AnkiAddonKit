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
        for repo in ("anki-stepwise", "anki-skim", "anki-exam-timeline", "anki-glass", "anki-bare"):
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
        self.assertEqual(family.about("glass")["author"]["fullName"], "Abdel-Rahman Ibrahim")
        socials = family.about("glass")["author"]["socials"]
        self.assertEqual([s["name"] for s in socials], ["LinkedIn", "Instagram"])
        self.assertTrue(all(s["url"].startswith("https://") for s in socials))
        self.assertEqual(family.about("glass")["author"]["website"], "https://abdelrahmanibrahim.com")

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


class Window:
    """Enough of a Qt window for family.preferences."""

    def __init__(self, parent=None, tag=None):
        self.parent, self.tag = parent, tag

    def property(self, name):
        return self.tag if name == family.WINDOW_PROPERTY else None

    def parentWidget(self):
        return self.parent


def window_class(module: str):
    return type("Win", (Window,), {"__module__": module})


class PreferencesTest(unittest.TestCase):
    """⌘, opens the settings of the add-on whose window is in front."""

    def setUp(self):
        family._outside.update(registry=None, meta={})
        self.opened = []
        members = family.registry()["members"]
        members["stepwise"] = {"id": "stepwise", "dir": "1949793886",
                               "open_settings": lambda: self.opened.append("stepwise")}
        members["glass"] = {"id": "glass", "dir": "anki_glass", "schema": [{"section": "S", "fields": []}],
                            "open_page": lambda i, tab: self.opened.append((i, tab))}
        members["exam-timeline"] = {"id": "exam-timeline", "dir": "anki-exam-timeline"}
        self.mw = window_class("aqt.main")()

    def test_an_add_on_window(self):
        win = window_class("1949793886.ui")(self.mw)
        self.assertTrue(family.preferences(win))
        self.assertEqual(self.opened, ["stepwise"])
        # A message box over it (a plain Qt class) belongs to it too.
        box = window_class("PyQt6.QtWidgets")(win)
        self.assertEqual(family.window_owner(box), "stepwise")

    def test_anki_and_other_windows_keep_anki_preferences(self):
        self.assertFalse(family.preferences(self.mw))
        self.assertFalse(family.preferences(window_class("aqt.browser.browser")(self.mw)))
        self.assertFalse(family.preferences(window_class("123456.someone_else")(self.mw)))
        self.assertFalse(family.preferences(None))
        # An add-on of the family with no settings of its own.
        self.assertFalse(family.preferences(window_class("anki-exam-timeline.editor")(self.mw)))
        self.assertEqual(self.opened, [])

    def test_the_kit_window(self):
        shown = []
        kit_win = window_class("1949793886.kit.page")(self.mw, tag="glass")
        kit_win.show_addon = lambda i, tab: shown.append((i, tab))
        self.assertTrue(family.preferences(kit_win))
        self.assertEqual(shown, [("glass", "settings")])  # switches its own tab
        kit_win.tag = "stepwise"
        self.assertTrue(family.preferences(kit_win))
        self.assertEqual(self.opened, ["stepwise"])
        # An older copy's window has no tag: it isn't the add-on that opened it.
        self.assertIsNone(family.window_owner(window_class("1949793886.kit.page")(self.mw)))

    def test_a_schema_opens_the_kit_window_on_settings(self):
        self.assertTrue(family.preferences(window_class("anki_glass.log")(self.mw)))
        self.assertEqual(self.opened, [("glass", "settings")])

    def test_a_panel_of_its_own_opens_the_kit_window_on_settings(self):
        members = family.registry()["members"]
        members["skim"] = {"id": "skim", "dir": "anki-skim", "settings_page": {"script": "web/settings.js"},
                           "open_settings": lambda: self.opened.append("old way"),
                           "open_page": lambda i, tab: self.opened.append((i, tab))}
        self.assertTrue(family.preferences(window_class("anki-skim.window")(self.mw)))
        self.assertEqual(self.opened, [("skim", "settings")])


class HostedSettingsTest(unittest.TestCase):
    """An add-on's own Settings panel, in the kit's window."""

    def setUp(self):
        family._outside.update(registry=None, meta={})
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "web"))
        for name, text in (("settings.js", "panel();"), ("settings.css", ".x{}")):
            with open(os.path.join(self.tmp.name, "web", name), "w") as f:
                f.write(text)
        self.seen = []

        def bridge(msg):
            self.seen.append(msg)
            if msg.get("cmd") == "boom":
                raise RuntimeError("no")
            return {"settings": {"on": True}}

        family.registry()["members"]["skim"] = {
            "id": "skim", "dir": "anki-skim", "path": self.tmp.name, "kit": 1,
            "open_settings": lambda: None, "schema": None, "note": None, "open_page": None,
            "settings_page": {"script": "web/settings.js", "style": "web/settings.css", "bridge": bridge},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_assets_and_commands(self):
        self.assertEqual(family.settings_assets("skim"), (".x{}", "panel();"))
        self.assertIsNone(family.settings_assets("glass"))
        self.assertEqual(family.settings_command("skim", {"cmd": "settings"}), {"settings": {"on": True}})
        self.assertEqual(self.seen, [{"cmd": "settings"}])
        self.assertEqual(family.settings_command("skim", {"cmd": "boom"}), {"error": "no"})
        self.assertIn("error", family.settings_command(None, {"cmd": "settings"}))
        self.assertIn("error", family.settings_command("glass", {"cmd": "settings"}))

    def test_a_missing_script_is_no_panel(self):
        os.remove(os.path.join(self.tmp.name, "web", "settings.js"))
        self.assertIsNone(family.settings_assets("skim"))

    def test_the_page_hears_hosted_over_its_own_window(self):
        self.member_log()
        skim = next(a for a in family.about("skim")["addons"] if a["id"] == "skim")
        self.assertEqual(skim["settings"], "hosted")

    def member_log(self):
        with open(os.path.join(self.tmp.name, "CHANGELOG.md"), "w") as f:
            f.write("## [1.0.0]\n- x\n")


class GlassTest(unittest.TestCase):
    """An add-on's window asks AnkiGlass for glass behind it."""

    def setUp(self):
        family._outside.update(registry=None, meta={})
        family.registry()["members"]["stepwise"] = {"id": "stepwise", "dir": "1949793886"}
        self.asked = []

    def glass(self, put_glass):
        family.registry()["members"]["glass"] = {"id": "glass", "dir": "anki_glass", "glass_window": put_glass}

    def test_without_ankiglass(self):
        self.assertFalse(kit.glass(object()))
        # An older AnkiGlass, from before window glass.
        family.registry()["members"]["glass"] = {"id": "glass", "dir": "anki_glass"}
        self.assertFalse(kit.glass(object()))

    def test_ankiglass_takes_the_window_or_not(self):
        window = object()
        self.glass(lambda w: self.asked.append(w) or True)
        self.assertTrue(kit.glass(window))
        self.assertEqual(self.asked, [window])
        self.glass(lambda w: False)  # its setting is off, say
        self.assertFalse(kit.glass(window))

    def test_never_raises(self):
        def broken(_window):
            raise RuntimeError("no")

        self.glass(broken)
        self.assertFalse(kit.glass(object()))

    def test_the_theme_has_the_class(self):
        with open(os.path.join(KIT, "web", "glass.css"), encoding="utf-8") as f:
            self.assertIn(f":root.{family.GLASS_CLASS} {{", f.read())
        with open(os.path.join(KIT, "web", "kit.css"), encoding="utf-8") as f:
            self.assertIn('@import "./glass.css";', f.read())


class SettingsTest(unittest.TestCase):
    SCHEMA = [{"section": "S", "fields": [
        {"key": "on", "type": "switch", "label": "On"},
        {"key": "screens", "type": "multi", "label": "Screens",
         "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]},
        {"key": "side", "type": "choice", "label": "Side",
         "options": [{"value": "front", "label": "Front"}, {"value": "back", "label": "Back"}]},
        {"key": "tint", "type": "text", "label": "Tint"},
        {"key": "ink", "type": "color", "label": "Ink", "alpha": True},
    ]}]

    def test_check(self):
        clean, problems = settings.check(self.SCHEMA, {
            "on": 1, "screens": ["b", "zzz", "a"], "side": "front", "tint": "  red  ",
        })
        self.assertEqual(clean, {"on": True, "screens": ["a", "b"], "side": "front", "tint": "red"})
        self.assertEqual(problems, {})
        _clean, problems = settings.check(self.SCHEMA, {"side": "up", "tint": "", "screens": "a"})
        self.assertEqual(set(problems), {"side", "tint", "screens"})

    def test_colours(self):
        for ok in ["#ff9300", "#F90", "#ff930080", "rgba(0,0,0,0.38)", "rgb(10 20 30 / 50%)",
                   "hsl(120deg 50% 50%)", "transparent", " Transparent "]:
            clean, problems = settings.check(self.SCHEMA, {"ink": ok})
            self.assertEqual((clean, problems), ({"ink": ok.strip()}, {}), ok)
        for bad in ["", "bluish", "#ff93a", "#ff9300;", "rgba(0,0,0", "red; x", "url(x)", "#" + "f" * 70]:
            _clean, problems = settings.check(self.SCHEMA, {"ink": bad})
            self.assertEqual(problems, {"ink": "Use a colour like rgba(0,0,0,0.4)."}, bad)

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
