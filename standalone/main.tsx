// The kit's own window (py/page.py): every add-on's What's new and About,
// and Settings for an add-on without a page of its own. Built into
// py/web/page.js and page.css.

import { StrictMode, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "../web/kit.css";
import "./page.css";
import { selfOf, useKitAbout } from "../web/AddonDialog";
import type { KitCall, KitTab } from "../web/types";
import { SchemaSettings } from "./SchemaSettings";
import { AddonWindow } from "./Window";

type Pycmd = (arg: string, cb?: (result: unknown) => void) => boolean;

declare global {
  interface Window {
    pycmd?: Pycmd;
    KIT_PAGE?: { id: string; tab: KitTab };
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

  // Every command is about the add-on on show; "page" (from About's list)
  // switches to another one here instead of opening a window.
  const call = useMemo<KitCall>(
    () =>
      <T,>(op: string, args: Record<string, unknown> = {}) => {
        if (op === "page") {
          setId(String(args.id));
          setTab((args.tab as KitTab) ?? "news");
          window.scrollTo(0, 0);
          return Promise.resolve({} as T);
        }
        return send<T>(op, { id, ...args });
      },
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
        ) : !self && tab === "settings" ? (
          <div className="skeleton" style={{ height: 260, marginTop: 28, borderRadius: 12 }} />
        ) : undefined
      }
      onOpenSettings={self?.settings === "window" ? () => void call("open_settings").catch(() => undefined) : undefined}
    />
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Page />
  </StrictMode>,
);
