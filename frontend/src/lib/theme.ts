// Design Source colours that are needed as values in code (inline styles,
// Recharts strokes). Class-based colours live in index.css as @theme tokens.

export const ZINC_600 = "#52525b";
export const ZINC_300 = "#d4d4d8";

const COMPOUNDS: Record<string, { letter: string; color: string }> = {
  SOFT: { letter: "S", color: "#f12f32" },
  MEDIUM: { letter: "M", color: "#fbcc1c" },
  HARD: { letter: "H", color: ZINC_300 },
  INTERMEDIATE: { letter: "I", color: "#128330" },
  INTER: { letter: "I", color: "#128330" },
  WET: { letter: "W", color: "#1f6da1" },
};

export function compoundLetter(compound: string | null | undefined): string | null {
  return (compound && COMPOUNDS[compound.toUpperCase()]?.letter) || null;
}

export function compoundColor(compound: string | null | undefined): string {
  return (compound && COMPOUNDS[compound.toUpperCase()]?.color) || ZINC_600;
}

export interface TrackStatusStyle {
  label: string;
  /** Tailwind classes for the pill background and text. */
  className: string;
  pulse: boolean;
}

/** OpenF1 track status codes: 1 green; 2, 4, 6, 7 yellow (7 pulses); 5 red. */
export function trackStatusStyle(status: string | null | undefined): TrackStatusStyle {
  const yellow = "bg-flag-yellow text-zinc-950";
  switch (status) {
    case "1":
      return { label: "GREEN", className: "bg-emerald-500 text-zinc-950", pulse: false };
    case "2":
      return { label: "YELLOW", className: yellow, pulse: false };
    case "4":
      return { label: "SAFETY CAR", className: yellow, pulse: false };
    case "6":
      return { label: "VSC", className: yellow, pulse: false };
    case "7":
      return { label: "VSC ENDING", className: yellow, pulse: true };
    case "5":
      return { label: "RED FLAG", className: "bg-flag-red text-zinc-50", pulse: false };
    default:
      return { label: "UNKNOWN", className: "bg-zinc-800 text-zinc-400", pulse: false };
  }
}

const EVENT_TYPES: Record<string, { label: string; color: string }> = {
  degradation_warning: { label: "DEGRADATION", color: "#fbcc1c" },
  undercut_window: { label: "UNDERCUT", color: "#c084fc" },
  position_change: { label: "POSITION", color: "#38bdf8" },
  pace_drop: { label: "PACE DROP", color: "#f12f32" },
};

export function eventTypeLabel(type: string): string {
  return EVENT_TYPES[type]?.label ?? type.replace(/_/g, " ").toUpperCase();
}

export function eventTypeColor(type: string): string {
  return EVENT_TYPES[type]?.color ?? "#a1a1aa";
}

/** Event types whose card shows the strategy table of the event's first driver. */
export const STRATEGY_EVENT_TYPES = new Set(["degradation_warning", "undercut_window"]);
