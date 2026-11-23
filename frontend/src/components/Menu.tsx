import { type ReactNode, useEffect, useId, useRef, useState } from "react";

export const menuButton =
  "rounded border border-zinc-800 px-2 py-1 text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-40 disabled:hover:bg-transparent";
export const menuItem =
  "block w-full rounded px-2 py-1 text-left text-sm text-zinc-200 hover:bg-zinc-800 focus-visible:bg-zinc-800 focus-visible:outline-none disabled:opacity-40";

interface MenuProps {
  label: ReactNode;
  /** Accessible name of the toggle button. */
  ariaLabel: string;
  /** `data-guide` anchor for the first-visit guide. */
  guide?: string;
  /** Menu body; `close` hides it (call after an action). */
  children: (close: () => void) => ReactNode;
  align?: "left" | "right";
}

/** A toggle button with a popover; closes on Escape and on clicks outside. */
export function Menu({ label, ariaLabel, guide, children, align = "left" }: MenuProps) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-label={ariaLabel}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        data-guide={guide}
        className={menuButton}
        onClick={() => setOpen((o) => !o)}
      >
        {label}
      </button>
      {open && (
        <div
          id={id}
          role="menu"
          aria-label={ariaLabel}
          className={`absolute top-full z-40 mt-1 min-w-48 rounded-md border border-zinc-700 bg-card p-1 shadow-xl shadow-black/50 ${
            align === "right" ? "right-0" : "left-0"
          }`}
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

/** A dismissible one-line message under the status bar. */
export function Notice({ text, onDismiss, testId = "notice" }: { text: string; onDismiss: () => void; testId?: string }) {
  return (
    <div
      role="status"
      data-testid={testId}
      className="flex items-center justify-between gap-3 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-200"
    >
      <span>{text}</span>
      <button type="button" aria-label="Dismiss" className="px-1 text-zinc-500 hover:text-zinc-100" onClick={onDismiss}>
        ✕
      </button>
    </div>
  );
}
