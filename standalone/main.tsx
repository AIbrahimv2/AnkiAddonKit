// The kit's own window (py/page.py): every add-on's What's new, About and
// Settings (drawn from a schema, or by the add-on's own panel). Built into
// py/web/page.js and page.css.

import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "../web/kit.css";
import "./page.css";
import { selfOf, useKitAbout } from "../web/AddonDialog";
import { KIT_SETTINGS_EVENT, type KitCall, type KitTab } from "../web/types";
import { SchemaSettings } from "./SchemaSettings";
import { AddonWindow } from "./Window";

type Pycmd = (arg: string, cb?: (result: unknown) => void) => boolean;

declare global {
  interface Window {
    pycmd?: Pycmd;
    /** `hosted`: the add-on whose own Settings panel page.py put in. */
    KIT_PAGE?: { id: string; tab: KitTab; hosted?: string | null };
    /** For page.py: show another add-on, or tab, without a reload. */
    kitPage?: { show(to: { id: string; tab: KitTab }): void };
  }
}

const ready: Promise<Pycmd> = new Promise((resolve) => {
  const check = () => (window.pycmd ? resolve(window.pycmd) : setTimeout(check, 15));
  check();
});

function send<T>(op: string, args: Record<string, unknown>): Promise<T> {
  return ready.then(
    (pycmd) =>
      new Promise<T>((resolve, reject) => {
        pycmd(JSON.stringify({ cmd: "kit", op, ...args }), (raw) => {
          const reply = (raw ?? {}) as T & { error?: string };
          if (reply.error) reject(new Error(reply.error));
          else resolve(reply);
        });
      }),
  );
}

const params = new URLSearchParams(location.search);
const boot = window.KIT_PAGE ?? {
  id: params.get("id") ?? "glass",
  tab: (params.get("tab") as KitTab | null) ?? "settings",
};

function Page() {
  const [id, setId] = useState(boot.id);
  const [tab, setTab] = useState<KitTab>(boot.tab);

  // "page" (About's list, or ⌘,) switches add-on through page.py, which
  // calls this back, or loads the page again with that add-on's Settings.
  useEffect(() => {
    window.kitPage = {
      show: (to) => {
        setId(to.id);
        setTab(to.tab);
        window.scrollTo(0, 0);
      },
    };
  }, []);

  // Every command is about the add-on on show.
  const call = useMemo<KitCall>(
    () =>
      <T,>(op: string, args: Record<string, unknown> = {}) =>
        send<T>(op, { id, ...args }),
    [id],
  );

  const [about] = useKitAbout(call);
  const self = selfOf(about);

  return (
    <AddonWindow
      key={id}
      call={call}
      tab={tab}
      onTab={setTab}
      settings={
        self?.settings === "page" ? (
          <SchemaSettings call={call} onClose={() => void send("close", {})} />
        ) : self?.settings === "hosted" ? (
          <HostedSettings id={self.id} />
        ) : !self && tab === "settings" ? (
          <div className="skeleton" style={{ height: 260, marginTop: 28, borderRadius: 12 }} />
        ) : undefined
      }
      onOpenSettings={self?.settings === "window" ? () => void call("open_settings").catch(() => undefined) : undefined}
    />
  );
}

/** The add-on's own Settings panel (its script, which page.py put in the
 *  page, calls provideSettings). Another add-on's needs the page again. */
function HostedSettings(props: { id: string }) {
  const el = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  const here = boot.hosted === props.id;

  useEffect(() => {
    if (!here) {
      void send("page", { id: props.id, tab: "settings" }).catch(() => undefined);
      return;
    }
    let unmount: (() => void) | null = null;
    const mount = () => {
      const panel = window.kitSettings;
      if (unmount || !panel || panel.id !== props.id || !el.current) return;
      unmount = panel.mount(el.current, { close: () => void send("close", {}).catch(() => undefined) });
      setShown(true);
    };
    mount();
    window.addEventListener(KIT_SETTINGS_EVENT, mount);
    return () => {
      window.removeEventListener(KIT_SETTINGS_EVENT, mount);
      unmount?.();
    };
  }, [props.id, here]);

  return (
    <>
      {!shown && <div className="skeleton" style={{ height: 260, marginTop: 28, borderRadius: 12 }} />}
      <div className="kit-hosted" ref={el} />
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Page />
  </StrictMode>,
);
