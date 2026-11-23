# Notes for agents

The kit AIbrahimv2's Anki add-ons share (see README.md). It isn't an add-on
itself: `sync.py` copies it into each add-on repo (`src/kit/`, and
`web/src/kit/` for add-ons with a page).

- **Change it here, never in a copy.** Then `npm run build` (when `web/` or
  `standalone/` changed), `python3 -m unittest discover tests`, and
  `python3 sync.py ../anki-stepwise ../anki-skim ../anki-exam-timeline ../anki-glass ../anki-bare`.
  Rebuild and test each add-on you synced; each add-on's `build.sh` warns
  when its copy is behind.
- **Bump `KIT_VERSION`** in `py/family.py` with every change that ships.
- **Note it in each add-on.** A change users will notice gets a line under
  `## [Unreleased]` in the `CHANGELOG.md` of every add-on you synced it
  into, in their terms, so it goes out with each one's next release.
- **Copies must get along.** Users may have add-ons carrying different kit
  versions at once. They meet only through the registry on `mw`
  (`family.registry()`): keep it plain values and functions, and add fields
  rather than change them. A change of shape needs a new `PROTOCOL`.
- **Never in the web view:** `<input type="date">`, `<select>`,
  `<input type="color">` or other native-popup controls. They crash Anki's
  web view on macOS.
- **Online only through Anki:** AnkiWeb's update check
  (`mw.backend.get_addon_info`) while About is open, and Anki's installer.
  Nothing else.
- **UI copy:** sentence case, no "·" separators, plain words.
- **Screenshots are made on the Mac.** `screenshots/on-mac.sh`, run from an
  add-on's root, runs its `tools/screenshots.py` there (over SSH from the
  Linux machine, into a mirror in `~/Documents/Projects/anki/work/shots-mirror`), on AnkiGlass's glass.
- **Trying a change in the Mac's real Anki:** `tools/to-mac.sh`, run from
  an add-on's root (or from here with repo names), builds its page and
  mirrors its `src/` to `~/Documents/Projects/anki/work/addons-live/<repo>` on the Mac, where Anki's
  `addons21` links to it. `--restart` restarts Anki. After syncing the kit,
  run it for each add-on you synced.
- The release steps for the add-ons are in the `anki-addon-release` skill
  (in the AnkiStepwise repo).
