import { useEffect, useState } from "react";
import { api, isAbortError, SettingsRejected } from "../api/client";
import type { CommentaryStatus, SettingsResponse } from "../api/types";

const LANG_LABELS: Record<string, string> = { en: "English", "zh-TW": "繁體中文" };

interface SettingsSheetProps {
  onClose: () => void;
  /** Called after a successful save, so the dashboard reloads the current lap. */
  onSaved: (settings: SettingsResponse) => void;
}

/** The read-only narrator line: the narrator and every key or address stay on the server. */
export function commentaryStatusText(c: CommentaryStatus): string {
  if (c.narrator === "none") return "Off — AUGUR_NARRATOR is none";
  const name = c.llm_model ? `${c.narrator} · ${c.llm_model}` : c.narrator;
  if (c.configured) return `${name} — Configured`;
  return c.missing ? `${name} — Not configured — set ${c.missing} in .env` : `${name} — Not configured`;
}

const field = "flex flex-col gap-1";
const label = "text-[10px] font-bold tracking-wider text-zinc-500";
const select = "rounded border border-zinc-800 bg-zinc-950 px-2 py-1 text-sm";

export function SettingsSheet({ onClose, onSaved }: SettingsSheetProps) {
  const [loaded, setLoaded] = useState<SettingsResponse | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [model, setModel] = useState("");
  const [lang, setLang] = useState("");
  const [saving, setSaving] = useState(false);
  const [rejected, setRejected] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api.settings(controller.signal).then(
      (s) => {
        setLoaded(s);
        setModel(s.model);
        setLang(s.commentary_lang);
      },
      (err: unknown) => {
        if (!isAbortError(err)) setLoadError(true);
      },
    );
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const save = async () => {
    setSaving(true);
    setRejected(null);
    try {
      const saved = await api.putSettings({ model, commentary_lang: lang, data_source: "replay" });
      onSaved(saved);
    } catch (err) {
      setRejected(err instanceof SettingsRejected ? err.detail : "Could not save the settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <aside
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
      data-testid="settings-sheet"
      className="fixed inset-y-0 right-0 z-40 flex w-80 max-w-full flex-col gap-4 border-l border-zinc-800 bg-card p-4 text-zinc-100 shadow-2xl"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold tracking-widest">SETTINGS</h2>
        <button type="button" aria-label="Close settings" className="text-zinc-400 hover:text-zinc-100" onClick={onClose}>
          ✕
        </button>
      </div>

      {loadError && (
        <p role="alert" className="text-sm text-flag-red">
          Could not load the settings
        </p>
      )}
      {!loaded && !loadError && <p className="text-sm text-zinc-400">Loading...</p>}

      {loaded && (
        <>
          <label className={field}>
            <span className={label}>MODEL</span>
            <select aria-label="Model" className={select} value={model} onChange={(e) => setModel(e.target.value)}>
              {loaded.models.map((m) => (
                <option key={m.name} value={m.name} disabled={!m.trained}>
                  {m.name}
                  {m.author ? ` — ${m.author}` : ""}
                  {m.trained ? "" : " (not trained)"}
                </option>
              ))}
            </select>
          </label>

          <label className={field}>
            <span className={label}>COMMENTARY LANGUAGE</span>
            <select aria-label="Commentary language" className={select} value={lang} onChange={(e) => setLang(e.target.value)}>
              {loaded.commentary_langs.map((l) => (
                <option key={l} value={l}>
                  {LANG_LABELS[l] ?? l}
                </option>
              ))}
            </select>
          </label>

          <label className={field}>
            <span className={label}>DATA SOURCE</span>
            <select aria-label="Data source" className={select} value="replay" onChange={() => {}}>
              {loaded.data_sources.map((s) => (
                <option key={s.name} value={s.name} disabled={!s.available}>
                  {s.name === "replay" ? "Replay" : "Live"}
                  {s.available ? "" : " — Coming later"}
                </option>
              ))}
            </select>
          </label>

          <div className={field}>
            <span className={label}>COMMENTARY</span>
            <p data-testid="commentary-status" className="text-sm text-zinc-300">
              {commentaryStatusText(loaded.commentary)}
            </p>
            <p className="text-[11px] text-zinc-500">Set on the server; keys and server addresses never reach the browser.</p>
          </div>

          <div className="mt-auto flex items-center gap-3">
            <button
              type="button"
              disabled={saving}
              onClick={save}
              className="rounded border border-zinc-600 px-3 py-1 text-sm font-bold hover:bg-zinc-800 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            {rejected && (
              <span role="alert" data-testid="settings-error" className="text-sm text-flag-red">
                {rejected}
              </span>
            )}
          </div>
        </>
      )}
    </aside>
  );
}
