# AnkiAddonKit

What AIbrahimv2's Anki add-ons share, so they look and behave like one
family: [Stepwise](https://github.com/AIbrahimv2/AnkiStepwise),
[Skim](https://github.com/AIbrahimv2/AnkiSkim),
[Exam Timeline](https://github.com/AIbrahimv2/AnkiExamTimeline),
[AnkiGlass](https://github.com/AIbrahimv2/AnkiGlass) and
[AnkiBare](https://github.com/AIbrahimv2/AnkiBare).

- **One look.** The theme (built on Anki's own light and dark colours) and
  the controls: buttons, the search box, switches, menus, dialogs, toasts,
  the keys list, settings rows and a colour picker (`ColorField`, never the
  native one, which crashes Anki), in CSS and React.
- **One window for Settings, What's new and About.** A window of its own
  (the kit's), whichever add-on opens it, with a tab for each: Settings;
  What's new, each add-on's changelog laid out one release a row; and
  About, which links to its code and issues, says whether AnkiWeb has an
  update, and lists the other add-ons with an Install button. AnkiGlass's
  Settings are described by a schema the kit draws; Stepwise's and Skim's
  are their own panels, which the kit puts in its window.
- **⌘, opens the add-on's Settings.** With one of the add-ons' windows in
  front, ⌘, (Anki's Preferences) opens that add-on's Settings, and Anki's
  own anywhere else.
- **One notice after updates.** After Anki starts, one card at the bottom
  of the main window says which add-ons were updated ("Stepwise 1.2.0 and
  Skim 1.1.0 were updated. See what's new"), once per version. The add-on's
  What's new tab keeps a dot until it's opened.

Nothing goes online except through Anki itself: update checks use Anki's own
AnkiWeb check, only while the About tab is open, and installs use Anki's
own installer. The list of add-ons and each one's changelog ship inside the
packages.

## How an add-on uses it

Check it out beside the add-ons as `anki-addon-kit` (their `build.sh` looks
for `../anki-addon-kit`). Anki add-ons can't depend on each other, so each
one carries a copy: `sync.py` copies the Python into the add-on's `src/kit/`
and, for an add-on with a web page, the styles and components into
`web/src/kit/`.

```bash
npm install && npm run build                  # the kit's own page, into py/web/
python3 sync.py ../anki-stepwise ../anki-skim # copy the kit in
python3 sync.py --check ../anki-stepwise      # is that copy current?
```

In the add-on's `__init__.py`:

```python
from . import kit

# Settings the kit draws from a schema (py/settings.py):
kit.register("glass", schema=SCHEMA, note="Changes apply after Anki restarts.")
# or a panel of the add-on's own, built into web/settings.js and .css:
kit.register("stepwise", settings_page={
    "script": "web/settings.js", "style": "web/settings.css", "bridge": handle})
# Either way, Anki's Config button opens them:
mw.addonManager.setConfigAction(__name__, lambda: kit.open_page(tab="settings"))
```

`handle(msg)` answers the panel's own commands (`{"cmd": ..., ...}`, as its
pycmd sends them; `"kit"` stays the kit's), whether or not the add-on's
window is open. The panel's script, a second bundle beside the add-on's
page, hands the panel to the kit's window:

```tsx
import { provideSettings } from "./kit/hosted";
import { SettingsFoot } from "./kit/settings"; // Restore defaults, Close, Save

provideSettings("stepwise", (host) => <MySettings onClose={host.close} />);
```

The window has the kit's theme and controls already, so the panel's
stylesheet brings only the add-on's own rules.

In the add-on's bridge, for its page's ⋯ menu:

```python
def cmd_kit(self, msg):
    return kit.command(msg)
```

and in the page:

```tsx
import "./kit/kit.css"; // before the add-on's own styles
import { openKitWindow, selfOf, useKitAbout } from "./kit/AddonDialog";

const kitCall: KitCall = (op, args) => call("kit", { op, ...args });
openKitWindow(kitCall, "settings"); // or "news", "about": the kit's window
const unseen = !!selfOf(useKitAbout(kitCall)[0])?.unseen; // a dot on ⋯
```

For AnkiGlass's glass behind a window of the add-on's own, when AnkiGlass is
installed (on a Mac) and its "Glass on add-on windows" is on, ask while
making the window, after its web view and before it shows or loads its page:

```python
self.web = AnkiWebView(self, title="stepwise")
kit.glass(self)
```

(The kit's own window asks for itself.)

AnkiGlass then puts `kit-glass` on the page's root, and the kit's theme
(`web/glass.css`) clears its background and turns the panels to glass. An
add-on's own stylesheet covers what the theme can't know about, under
`:root.kit-glass`: text on a `--text` fill takes `--solid`, and things that
float over the page take `--float`. Nothing can be frosted: Anki's web view
draws no `backdrop-filter` on a see-through page. So a bar the page scrolls
under turns `--solid` while it's stuck, through an underlay and a
scroll-state query (the pattern is in `glass.css`). A page that draws cards in frames of its own calls
`window.kitGlassCard?.(frame.contentWindow)` once a card is drawn: AnkiGlass
defines it while its "Glass behind the card" is on, and it makes the card
see-through as the reviewer's is.

For a resource's logo beside its name (Bootcamp, Sketchy, UWorld, ...: the
ones AnKing's decks tag cards with), `resources.tsx` looks it up by the name
however it's written (`#SketchyPharm`, `OME banner`, `Bootcamp (Step 1)`)
and draws it at 18px (the ones in one dark colour in the text's colour, so
they show in dark mode too):

```tsx
import { ResourceIcon, resourceImg } from "./kit/resources";
<ResourceIcon name={resource.label} />    // in React; nothing if it has none
<ResourceIcon name={label} keepRoom />    // or its room, so a list's names line up
row.append(resourceImg(label) ?? "");     // in plain DOM (keepRoom too)
```

The logos are in `web/resources/`, each the brand's own icon from its
website (an SVG cut to its symbol where there was one, else its tab icon at
64px), bundled into the page that imports them. The names and logos belong
to their owners; the add-ons aren't affiliated with them.

`build.sh` puts `CHANGELOG.md` (Keep a Changelog) in the package: What's new
reads it, and its newest released version is the add-on's version.

## Adding an add-on

Add it to `catalog.json` (id, name, emoji, tagline, about, AnkiWeb id,
GitHub repo, folder names, platforms) and bump `updated`. Every add-on picks
up the newest catalog any installed one brings, so the next release of any
of them announces it.

## Working on the kit

- `web/`: the theme, controls, the colour picker (`color.tsx`; a schema
  row of type `"color"` uses it too), settings rows and their footer
  (`settings.tsx`), what a page needs to open the kit's window
  (`AddonDialog.tsx`) and to hand it a Settings panel (`hosted.tsx`), and
  the look on AnkiGlass's glass (`glass.css`).
- `standalone/`: the kit's own window's page (`Window.tsx`: What's new,
  About, Settings from a schema or an add-on's own panel), built into
  `py/web/`.
- `py/`: `family.py` (the registry the add-ons share at runtime, versions,
  what you've seen, AnkiWeb), `changelog.py`, `settings.py` (schema
  settings), `page.py` (the window and the notice).
- `tools/preview.py` plus `npm run dev` shows the window in a browser with
  the add-ons' real changelogs: http://localhost:5184/?id=glass&tab=settings
  (`&theme=dark` for dark mode).
- Tests: `python3 -m unittest discover tests`.

Bump `KIT_VERSION` in `py/family.py` with each change (the newest copy
installed leads), and `PROTOCOL` only if the registry's shape changes.
