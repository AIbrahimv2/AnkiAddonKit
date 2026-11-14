// Settings described by the add-on's schema (py/settings.py), for the kit's
// own window. "action" rows are buttons that run the add-on's function of
// that key (turning AnkiGlass off, say); the schema is fetched again after
// one, since it may follow the add-on's state.

import { Check, LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Switch } from "../web/controls";
import { Block, Choice, Row, Section } from "../web/settings";
import type { KitCall } from "../web/types";

interface Option {
  value: string;
  label: string;
}

interface Field {
  key: string;
  type: "switch" | "multi" | "choice" | "text" | "action";
  label: string;
  hint?: string;
  options?: Option[];
  mono?: boolean;
  placeholder?: string;
  /** An action row's button text; without it the row is only text. */
  button?: string;
}

interface Loaded {
  schema: { section: string; fields: Field[] }[];
  values: Record<string, unknown>;
  defaults: Record<string, unknown>;
  note: string | null;
}

type Values = Record<string, unknown>;

export function SchemaSettings(props: { call: KitCall; onClose: () => void }) {
  const { call } = props;
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [v, setV] = useState<Values>({});
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    call<Loaded>("settings").then((r) => {
      setLoaded(r);
      setV(r.values);
    });
  }, [call]);

  const dirty = useMemo(() => !!loaded && JSON.stringify(v) !== JSON.stringify(loaded.values), [v, loaded]);
  const isDefault = useMemo(
    () => !!loaded && Object.keys(loaded.defaults).every((k) => JSON.stringify(v[k]) === JSON.stringify(loaded.defaults[k])),
    [v, loaded],
  );

  const set = (key: string, value: unknown) => {
    setV((old) => ({ ...old, [key]: value }));
    setProblems(({ [key]: _gone, ...rest }) => rest);
    setSaved(false);
  };

  const save = async () => {
    setSaving(true);
    try {
      const r = await call<{ problems?: Record<string, string>; saved?: boolean }>("save_settings", { values: v });
      if (r.problems) setProblems(r.problems);
      else if (r.saved && loaded) {
        setLoaded({ ...loaded, values: v });
        setSaved(true);
      }
    } finally {
      setSaving(false);
    }
  };

  const act = async (key: string) => {
    setRunning(key);
    setMessage(null);
    try {
      const r = await call<{ message: string | null }>("action", { key });
      setMessage(r.message);
      // Only the rows change: what you've typed but not saved stays.
      const fresh = await call<Loaded>("settings");
      setLoaded((old) => (old ? { ...fresh, values: old.values } : fresh));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(null);
    }
  };

  if (!loaded) return <div className="skeleton" style={{ height: 260, borderRadius: 12 }} />;

  return (
    <>
      <div className="settings">
        {loaded.note && <p className="kit-note">{loaded.note}</p>}
        {loaded.schema.map((s) => (
          <Section key={s.section} title={s.section}>
            {s.fields.map((f) => (
              <FieldRow
                key={f.key}
                field={f}
                value={v[f.key]}
                problem={problems[f.key]}
                onChange={(x) => set(f.key, x)}
                running={running}
                onAct={act}
              />
            ))}
          </Section>
        ))}
      </div>
      {/* Kept in view at the bottom of the window. */}
      <div className="kit-foot">
        <div className="modal-actions settings-actions">
          <button
            type="button"
            className="btn ghost"
            disabled={isDefault}
            onClick={() => {
              setV({ ...v, ...loaded.defaults });
              setProblems({});
              setSaved(false);
            }}
          >
            Restore defaults
          </button>
          <span className="spacer" />
          {message ? (
            <span className="kit-status kit-message">{message}</span>
          ) : (
            saved &&
            !dirty && (
              <span className="kit-status ok">
                <Check size={14} strokeWidth={2.5} /> Saved
              </span>
            )
          )}
          <button type="button" className="btn" onClick={props.onClose}>
            Close
          </button>
          <button type="button" className="btn primary" disabled={!dirty || saving} onClick={save}>
            Save
          </button>
        </div>
      </div>
    </>
  );
}

function FieldRow(props: {
  field: Field;
  value: unknown;
  problem?: string;
  onChange: (v: unknown) => void;
  running: string | null;
  onAct: (key: string) => void;
}) {
  const { field: f, value, problem, onChange } = props;
  if (f.type === "action")
    return (
      <Row label={f.label} hint={f.hint}>
        {f.button &&
          (props.running === f.key ? (
            <span className="kit-status">
              <LoaderCircle size={14} className="spin" />
            </span>
          ) : (
            <button type="button" className="btn sm" disabled={!!props.running} onClick={() => props.onAct(f.key)}>
              {f.button}
            </button>
          ))}
      </Row>
    );
  if (f.type === "switch")
    return (
      <Row label={f.label} hint={f.hint} problem={problem}>
        <Switch checked={!!value} label="" onChange={onChange} />
      </Row>
    );
  if (f.type === "choice")
    return (
      <Row label={f.label} hint={f.hint} problem={problem}>
        <Choice value={String(value)} options={f.options ?? []} onChange={onChange} />
      </Row>
    );
  if (f.type === "multi") {
    const on = new Set(Array.isArray(value) ? (value as string[]) : []);
    return (
      <Block label={f.label} hint={f.hint} problem={problem}>
        <div className="kit-chips">
          {(f.options ?? []).map((o) => (
            <button
              key={o.value}
              type="button"
              role="checkbox"
              aria-checked={on.has(o.value)}
              className={`kit-chip${on.has(o.value) ? " on" : ""}`}
              onClick={() => {
                const next = new Set(on);
                if (next.has(o.value)) next.delete(o.value);
                else next.add(o.value);
                onChange((f.options ?? []).map((x) => x.value).filter((x) => next.has(x)));
              }}
            >
              {on.has(o.value) && <Check size={13} strokeWidth={2.6} />}
              {o.label}
            </button>
          ))}
        </div>
      </Block>
    );
  }
  return (
    <Row label={f.label} hint={f.hint} problem={problem}>
      <input
        className={`set-input${f.mono ? " mono" : ""}${problem ? " bad" : ""}`}
        value={String(value ?? "")}
        placeholder={f.placeholder}
        spellCheck={false}
        onChange={(e) => onChange(e.target.value)}
        aria-label={f.label}
      />
    </Row>
  );
}
