# anki-addon-kit

What AIbrahimv2's Anki add-ons share, so they look and behave like one
family: [Stepwise](https://github.com/AIbrahimv2/AnkiStepwise),
[Skim](https://github.com/AIbrahimv2/AnkiSkim),
[Exam Timeline](https://github.com/AIbrahimv2/AnkiExamTimeline),
[AnkiGlass](https://github.com/AIbrahimv2/AnkiGlass) and
[AnkiBare](https://github.com/AIbrahimv2/AnkiBare).

- **One look.** The theme (built on Anki's own light and dark colours) and
  the controls: buttons, the search box, switches, menus, dialogs, toasts,
  the keys list and settings rows, in CSS and React.
- **One Settings, What's new and About dialog.** Each add-on's Settings sit
  beside its changelog and an About tab that links to its code and issues,
  says whether AnkiWeb has an update, and lists the other add-ons with an
  Install button. Add-ons without a page of their own (AnkiGlass, AnkiBare)
  open it in the kit's own window, with their settings described by a
  schema.
- **One notice after updates.** After Anki starts, one card at the bottom
  of the main window says which add-ons were updated ("Stepwise 1.2.0 and
  Skim 1.1.0 were updated. See what's new"), once per version. The add-on's
  What's new tab keeps a dot until it's opened.

Nothing goes online except through Anki itself: update checks use Anki's own
AnkiWeb check, only while the About tab is open, and installs use Anki's
own installer. The list of add-ons and each one's changelog ship inside the
packages.

## How an add-on uses it

Anki add-ons can't depend on each other, so each one carries a copy:
`sync.py` copies the Python into the add-on's `src/kit/` and, for an add-on
with a web page, the styles and components into `web/src/kit/`.

```bash
npm install && npm run build                  # the kit's own page, into py/web/
python3 sync.py ../anki-tag-queue ../anki-skim # copy the kit in
python3 sync.py --check ../anki-tag-queue      # is that copy current?
```

In the add-on's `__init__.py`:

```python
from . import kit

kit.register("stepwise", open_settings=ui.open_settings)  # its id in catalog.json
# or, with settings the kit's window shows:
kit.register("glass", schema=SCHEMA, note="Changes apply after Anki restarts.")
mw.addonManager.setConfigAction(__name__, lambda: kit.open_page(tab="settings"))
```

In its bridge, for a page that shows the dialog:

```python
def cmd_kit(self, msg):
    return kit.command(msg)
```

and in the page:

```tsx
import "./kit/kit.css"; // before the add-on's own styles
import { AddonDialog, selfOf, useKitAbout } from "./kit/AddonDialog";

const kitCall: KitCall = (op, args) => call("kit", { op, ...args });
<AddonDialog call={kitCall} tab={tab} onTab={setTab} onClose={close}
             settings={<MySettings />} settingsFooter={<SaveButtons />} />
```

`build.sh` puts `CHANGELOG.md` (Keep a Changelog) in the package: What's new
reads it, and its newest released version is the add-on's version.

## Adding an add-on

Add it to `catalog.json` (id, name, emoji, tagline, about, AnkiWeb id,
GitHub repo, folder names, platforms) and bump `updated`. Every add-on picks
up the newest catalog any installed one brings, so the next release of any
of them announces it.

## Working on the kit

- `web/`: the theme, controls and dialog (`AddonDialog.tsx`).
- `standalone/`: the kit's own window's page, built into `py/web/`.
- `py/`: `family.py` (the registry the add-ons share at runtime, versions,
  what you've seen, AnkiWeb), `changelog.py`, `settings.py` (schema
  settings), `page.py` (the window and the notice).
- `tools/preview.py` plus `npm run dev` shows the window in a browser with
  the add-ons' real changelogs: http://localhost:5184/?id=glass&tab=settings
  (`&theme=dark` for dark mode).
- Tests: `python3 -m unittest discover tests`.

Bump `KIT_VERSION` in `py/family.py` with each change (the newest copy
installed leads), and `PROTOCOL` only if the registry's shape changes.
