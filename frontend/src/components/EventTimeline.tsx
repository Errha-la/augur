import type { RaceEvent } from "../api/types";
import { eventTypeColor, eventTypeLabel } from "../lib/theme";

interface EventTimelineProps {
  lap: number;
  totalLaps: number;
  /** Events at lap <= current lap (the /events response for that lap). */
  events: RaceEvent[];
  focusCode: string | null;
  focusColor: string | null;
  onJump: (lap: number) => void;
}

const TYPES = ["degradation_warning", "undercut_window", "position_change", "pace_drop"];

/** Track from lap 1 to total_laps with one clickable marker per event so far. */
export function EventTimeline({ lap, totalLaps, events, focusCode, focusColor, onJump }: EventTimelineProps) {
  const span = Math.max(totalLaps - 1, 1);
  const stackIndex = new Map<string, number>();
  const perLap = new Map<number, number>();
  // Oldest first, so markers on the same lap stack upward in race order.
  for (const e of [...events].reverse()) {
    const n = perLap.get(e.lap) ?? 0;
    stackIndex.set(e.id, n);
    perLap.set(e.lap, n + 1);
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-[10px] tracking-wider text-zinc-500">EVENTS</span>
      <div data-testid="event-timeline" className="relative h-9 flex-1">
        <div className="absolute inset-x-0 bottom-1 h-px bg-zinc-800" />
        <div
          className="absolute bottom-1 h-px bg-zinc-500"
          style={{ left: 0, width: `${((Math.min(lap, totalLaps) - 1) / span) * 100}%` }}
        />
        {events
          .filter((e) => e.lap <= lap)
          .map((e) => {
            const highlighted = focusCode !== null && e.drivers.includes(focusCode);
            const color = eventTypeColor(e.type);
            return (
              <button
                key={e.id}
                type="button"
                data-testid="timeline-marker"
                data-lap={e.lap}
                data-type={e.type}
                data-highlight={highlighted || undefined}
                aria-label={`Lap ${e.lap}: ${eventTypeLabel(e.type)} — ${e.title}`}
                title={`Lap ${e.lap} · ${eventTypeLabel(e.type)} · ${e.title}`}
                onClick={() => onJump(e.lap)}
                className="absolute h-2.5 w-2.5 -translate-x-1/2 rounded-full hover:scale-150"
                style={{
                  left: `${((e.lap - 1) / span) * 100}%`,
                  bottom: 4 + (stackIndex.get(e.id) ?? 0) * 7,
                  backgroundColor: color,
                  boxShadow: highlighted && focusColor ? `0 0 0 2px ${focusColor}` : undefined,
                }}
              />
            );
          })}
      </div>
      <span className="hidden gap-2 text-[10px] lg:flex">
        {TYPES.map((t) => (
          <span key={t} className="flex items-center gap-1 text-zinc-500">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: eventTypeColor(t) }} />
            {eventTypeLabel(t)}
          </span>
        ))}
      </span>
    </div>
  );
}
