import { EVENT_TYPES } from "../canvas/registry";
import { eventTypeColor, eventTypeLabel } from "../lib/theme";

export const NO_MATCHING_EVENTS = "No matching events yet";

/** The types an events widget shows: its setting, or every type when unset. */
export function shownTypes(types: string[] | undefined): readonly string[] {
  return types ?? EVENT_TYPES;
}

/** Title-bar toggle chips for an events widget's type filter. */
export function EventTypeChips({ types, onChange }: { types: string[] | undefined; onChange: (types: string[] | undefined) => void }) {
  const on = new Set(shownTypes(types));
  const toggle = (type: string) => {
    const next = EVENT_TYPES.filter((t) => (t === type ? !on.has(t) : on.has(t)));
    onChange(next.length === EVENT_TYPES.length ? undefined : next);
  };
  return (
    <div role="group" aria-label="Event types shown" className="flex flex-wrap gap-1">
      {EVENT_TYPES.map((type) => {
        const pressed = on.has(type);
        return (
          <button
            key={type}
            type="button"
            aria-pressed={pressed}
            onClick={() => toggle(type)}
            className={`rounded border px-1 text-[9px] font-bold tracking-wider ${
              pressed ? "border-current" : "border-zinc-800 opacity-40"
            }`}
            style={{ color: eventTypeColor(type) }}
          >
            {eventTypeLabel(type)}
          </button>
        );
      })}
    </div>
  );
}
