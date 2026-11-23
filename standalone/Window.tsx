// The kit's own window (py/page.py): What's new, About and Settings (from
// the add-on's schema, or its own panel). Every add-on opens them here; the
// notice after updates does too. Styled by page.css.

import { Bug, Check, Code2, ExternalLink, Info, LoaderCircle, Settings2, Sparkles, Star } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { announceKitChange, listingUrl, selfOf, useKitAbout } from "../web/AddonDialog";
import { Inline } from "../web/markdown";
import { Row, Section } from "../web/settings";
import { Signature } from "../web/Signature";
import type { KitAbout, KitAddon, KitCall, KitRelease, KitTab, KitUpdate } from "../web/types";

/** Back to the top of what scrolls: the content area, or Settings' rows
 * (page.css). The window itself doesn't scroll. */
export function scrollToTop() {
  document.querySelectorAll<HTMLElement>(".kit-main, .kit-main .settings").forEach((el) => {
    el.scrollTop = 0;
  });
}

export function AddonWindow(props: {
  call: KitCall;
  tab: KitTab;
  onTab: (tab: KitTab) => void;
  /** Settings the window shows (a schema's, or the add-on's own panel). */
  settings?: ReactNode;
  /** Settings in the add-on's own window (an older copy of the add-on,
   *  from before they were a tab here): a button opens them. */
  onOpenSettings?: () => void;
}) {
  const { call } = props;
  const [about, reload] = useKitAbout(call);
  const self = selfOf(about);
  const open = useCallback((url: string) => void call("open", { url }).catch(() => undefined), [call]);

  const tabs: { id: KitTab; label: string; icon: ReactNode; dot?: boolean }[] = [
    { id: "news", label: "What's new", icon: <Sparkles size={15} />, dot: !!self?.unseen },
    { id: "about", label: "About", icon: <Info size={15} /> },
    ...(props.settings ? [{ id: "settings" as const, label: "Settings", icon: <Settings2 size={15} /> }] : []),
  ];
  const tab = tabs.some((t) => t.id === props.tab) ? props.tab : tabs[0].id;

  // Versions that were new when the window opened keep their badge after
  // What's new marks them read.
  const [newAtOpen, setNewAtOpen] = useState<{ id: string; versions: Set<string> } | null>(null);
  useEffect(() => {
    if (self && newAtOpen?.id !== self.id)
      setNewAtOpen({ id: self.id, versions: new Set(self.changes.filter((r) => r.isNew && r.version).map((r) => r.version!)) });
  }, [self, newAtOpen?.id]);

  // Opening What's new marks it read, for this add-on's dot and the notice.
  // Only when it was asked for: not while it stands in for a tab that
  // hasn't loaded yet.
  useEffect(() => {
    if (props.tab !== "news" || !self?.unseen) return;
    call("seen", { id: self.id }).then(announceKitChange, () => undefined);
  }, [props.tab, self?.id, self?.unseen, call]);

  return (
    <div className="kit-window">
      <header className="kit-hero">
        <div className="kit-col kit-id">
          <span className="kit-tile lg" aria-hidden="true">{self?.emoji ?? ""}</span>
          <div className="kit-id-text">
            {self ? (
              <>
                <h1>
                  {self.name}
                  {self.version && <span className="kit-version">{self.version}</span>}
                </h1>
                <p className="kit-tagline">{self.tagline}</p>
              </>
            ) : (
              <>
                <div className="skeleton" style={{ width: 160, height: 20 }} />
                <div className="skeleton" style={{ width: 260, height: 13, marginTop: 8 }} />
              </>
            )}
          </div>
          {props.onOpenSettings && (
            <button type="button" className="btn sm" onClick={props.onOpenSettings}>
              <Settings2 size={14} /> Settings
            </button>
          )}
        </div>
      </header>

      <nav className="kit-nav">
        <div className="kit-col kit-nav-in" role="tablist">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={t.id === tab}
              onClick={() => {
                props.onTab(t.id);
                scrollToTop();
              }}
            >
              {t.icon}
              {t.label}
              {t.dot && <span className="kit-dot" aria-label="new" />}
            </button>
          ))}
        </div>
      </nav>

      <main className="kit-col kit-main" role="tabpanel">
        {tab === "settings" && <div className="kit-settings">{props.settings}</div>}
        {tab === "news" && (self ? <WhatsNew addon={self} wasNew={newAtOpen?.versions} onLink={open} /> : <Loading />)}
        {tab === "about" && (about && self ? <AboutTab about={about} self={self} call={call} onLink={open} reload={reload} /> : <Loading />)}
      </main>
    </div>
  );
}

function Loading() {
  return <div className="skeleton" style={{ height: 240, marginTop: 28, borderRadius: 12 }} />;
}

// --- what's new ----------------------------------------------------------------------

const SHOWN = 3;

function WhatsNew(props: { addon: KitAddon; wasNew?: Set<string>; onLink: (url: string) => void }) {
  const [all, setAll] = useState(false);
  const releases = props.addon.changes.filter((r) => r.sections.some((s) => s.items.length));
  if (!releases.length) return <div className="kit-empty">No changes are listed yet.</div>;
  const shown = all ? releases : releases.slice(0, SHOWN);
  const older = releases.length - shown.length;
  return (
    <div className="kit-releases">
      {shown.map((r, i) => (
        <Release
          key={r.version ?? `next-${i}`}
          release={{ ...r, isNew: r.isNew || (!!r.version && !!props.wasNew?.has(r.version)) }}
          onLink={props.onLink}
        />
      ))}
      {older > 0 && (
        <div className="kit-more">
          <button type="button" className="btn sm" onClick={() => setAll(true)}>
            Show {older} older {older === 1 ? "version" : "versions"}
          </button>
        </div>
      )}
    </div>
  );
}

/** Keep a Changelog's headings, each with its own colour. */
const KINDS = new Set(["added", "changed", "fixed", "removed", "deprecated", "security"]);

function Release(props: { release: KitRelease; onLink: (url: string) => void }) {
  const r = props.release;
  return (
    <article className="kit-release">
      <div className="kit-release-meta">
        <h3 className="kit-ver">{r.version ?? "Not released yet"}</h3>
        {r.date && <div className="kit-date">{formatDate(r.date)}</div>}
        {r.isNew && <span className="kit-badge">New</span>}
      </div>
      <div className="kit-release-body">
        {r.sections
          .filter((s) => s.items.length)
          .map((s, i) => {
            const kind = s.title.trim().toLowerCase();
            return (
              <section className="kit-rsec" key={i}>
                {s.title && <h4 className={`kit-kind ${KINDS.has(kind) ? kind : ""}`}>{s.title}</h4>}
                <ul>
                  {s.items.map((item, j) => (
                    <li key={j}>
                      <Inline text={item} onLink={props.onLink} />
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
      </div>
    </article>
  );
}

function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

// --- about -------------------------------------------------------------------------

/** Asks AnkiWeb (through Anki's own update check) once per opening, and
 *  waits for the answer by asking again. */
function useUpdates(call: KitCall): Record<string, KitUpdate> | null {
  const [updates, setUpdates] = useState<Record<string, KitUpdate> | null>(null);
  useEffect(() => {
    let alive = true;
    let tries = 0;
    const ask = () =>
      call<{ done: boolean; updates: Record<string, KitUpdate> }>("updates").then(
        (r) => {
          if (!alive) return;
          if (r.done) setUpdates(r.updates);
          else if (++tries < 40) setTimeout(ask, 500);
          else setUpdates({});
        },
        () => alive && setUpdates({}),
      );
    ask();
    return () => {
      alive = false;
    };
  }, [call]);
  return updates;
}

function AboutTab(props: {
  about: KitAbout;
  self: KitAddon;
  call: KitCall;
  onLink: (url: string) => void;
  reload: () => void;
}) {
  const { about, self, call, onLink } = props;
  const updates = useUpdates(call);
  const [installing, setInstalling] = useState<Set<string>>(new Set());

  // While an install runs, look again now and then: Anki says when it's
  // done, and the card then asks for a restart.
  const reload = useRef(props.reload);
  reload.current = props.reload;
  useEffect(() => {
    if (!installing.size) return;
    const t = setInterval(() => reload.current(), 1500);
    return () => clearInterval(t);
  }, [installing.size]);
  useEffect(() => {
    const done = [...installing].filter((id) => about.addons.find((a) => a.id === id)?.installed && updates?.[id] !== "available");
    if (done.length) setInstalling((s) => new Set([...s].filter((id) => !done.includes(id))));
  }, [about, installing, updates]);

  const install = (a: KitAddon) => {
    setInstalling((s) => new Set(s).add(a.id));
    call("install", { id: a.id }).catch(() =>
      setInstalling((s) => {
        const next = new Set(s);
        next.delete(a.id);
        return next;
      }),
    );
  };

  const others = about.addons.filter((a) => a.id !== self.id && (a.installed || a.ankiweb));
  const status = updates?.[self.id];

  return (
    <div className="kit-about">
      <section className="kit-intro">
        <p className="kit-about-text">{self.about}</p>
        <div className="kit-links">
          <button type="button" className="btn sm" onClick={() => onLink(`https://github.com/${self.github}`)}>
            <Code2 size={14} /> Source code
          </button>
          <button type="button" className="btn sm" onClick={() => onLink(`https://github.com/${self.github}/issues`)}>
            <Bug size={14} /> Report a problem
          </button>
          {self.ankiweb && (
            <button type="button" className="btn sm" onClick={() => onLink(`https://ankiweb.net/shared/info/${self.ankiweb}`)}>
              <Star size={14} /> Rate it on AnkiWeb
            </button>
          )}
        </div>
      </section>

      <div className="settings">
        <Section title="This add-on">
          <Row
            label={self.version ? `Version ${self.version}` : "Not released yet"}
            hint={
              self.dev
                ? "Runs from its own folder rather than from AnkiWeb, so Anki doesn't update it."
                : status === undefined
                  ? "Checking AnkiWeb for updates…"
                  : status === "available"
                    ? "A newer version is on AnkiWeb."
                    : status === "current"
                      ? "Up to date."
                      : "Couldn't reach AnkiWeb to check for updates."
            }
          >
            {status === "available" &&
              (installing.has(self.id) ? (
                <Busy label="Updating…" />
              ) : (
                <button type="button" className="btn sm primary" onClick={() => install(self)}>
                  Update
                </button>
              ))}
            {status === "current" && !self.dev && (
              <span className="kit-status ok">
                <Check size={14} strokeWidth={2.5} /> Up to date
              </span>
            )}
          </Row>
        </Section>
      </div>

      {others.length > 0 && (
        <section>
          <h3 className="kit-h">More add-ons by {about.author.name}</h3>
          <div className="kit-cards">
            {others.map((a) => (
              <div className="kit-card" key={a.id}>
                <div className="kit-card-top">
                  <span className="kit-tile" aria-hidden="true">{a.emoji}</span>
                  <div className="kit-card-text">
                    <button type="button" className="kit-name" onClick={() => onLink(listingUrl(a))} title="Open its page">
                      {a.name}
                      {a.unseen && <span className="kit-dot" aria-label="updated" />}
                      <ExternalLink size={11} />
                    </button>
                    <div className="kit-card-tag">{a.tagline}</div>
                  </div>
                </div>
                <div className="kit-card-foot">
                  <AddonStatus
                    addon={a}
                    update={updates?.[a.id]}
                    installing={installing.has(a.id)}
                    onInstall={() => install(a)}
                    onNews={() => void call("page", { id: a.id, tab: "news" }).catch(() => undefined)}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <footer className="kit-signoff">
        <p>Thanks for using {self.name}.</p>
        {about.author.website ? (
          // The signature and name open the author's website.
          <button
            type="button"
            className="kit-signature-link"
            title={about.author.website.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")}
            onClick={() => onLink(about.author.website!)}
          >
            <Signature className="kit-signature" label={`${about.author.fullName ?? about.author.name}'s website`} />
            {about.author.fullName && <span className="kit-signoff-name">{about.author.fullName}</span>}
          </button>
        ) : (
          <>
            <Signature className="kit-signature" label={`${about.author.fullName ?? about.author.name}'s signature`} />
            {about.author.fullName && <p className="kit-signoff-name">{about.author.fullName}</p>}
          </>
        )}
        {!!about.author.socials?.length && (
          <div className="kit-socials">
            {about.author.socials.map((s) => (
              <button type="button" key={s.url} onClick={() => onLink(s.url)}>
                <SocialIcon name={s.name} /> {s.name}
              </button>
            ))}
          </div>
        )}
      </footer>
    </div>
  );
}

// Lucide has no brand icons any more, so these two are drawn here in its
// style (24px grid, 2px strokes); anything else gets the external-link one.
function SocialIcon(props: { name: string }) {
  const svg = { width: 13, height: 13, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
  switch (props.name.toLowerCase()) {
    case "linkedin":
      return (
        <svg {...svg}>
          <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6z" />
          <rect width="4" height="12" x="2" y="9" />
          <circle cx="4" cy="4" r="2" />
        </svg>
      );
    case "instagram":
      return (
        <svg {...svg}>
          <rect width="20" height="20" x="2" y="2" rx="5" />
          <circle cx="12" cy="12" r="4" />
          <path d="M17.5 6.5h.01" />
        </svg>
      );
    default:
      return <ExternalLink size={13} aria-hidden="true" />;
  }
}

function AddonStatus(props: {
  addon: KitAddon;
  update: KitUpdate | undefined;
  installing: boolean;
  onInstall: () => void;
  onNews: () => void;
}) {
  const a = props.addon;
  if (props.installing) return <Busy label={a.installed ? "Updating…" : "Installing…"} />;
  if (!a.installed) {
    if (!a.supported) return <span className="kit-status">macOS only</span>;
    return (
      <button type="button" className="btn sm" onClick={props.onInstall}>
        Install
      </button>
    );
  }
  if (!a.enabled) return <span className="kit-status">Turned off</span>;
  if (!a.running) return <span className="kit-status">Restart Anki to start it</span>;
  if (props.update === "available")
    return (
      <button type="button" className="btn sm" onClick={props.onInstall}>
        Update
      </button>
    );
  if (a.unseen)
    return (
      <button type="button" className="btn sm" onClick={props.onNews}>
        <Sparkles size={13} /> What's new
      </button>
    );
  return (
    <span className="kit-status ok">
      <Check size={14} strokeWidth={2.5} /> Installed
    </span>
  );
}

function Busy(props: { label: string }) {
  return (
    <span className="kit-status">
      <LoaderCircle size={14} className="spin" /> {props.label}
    </span>
  );
}
