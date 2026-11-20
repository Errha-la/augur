import { useState } from "react";
import { api } from "../api/client";
import type { RaceEvent, StrategyResponse } from "../api/types";
import { useKeyedFetch } from "../hooks/useKeyedFetch";
import { eventTypeColor, eventTypeLabel, STRATEGY_EVENT_TYPES } from "../lib/theme";
import { StrategyTable } from "./StrategyTable";

export const NO_EVENTS = "No significant events yet";

interface IntelligencePanelProps {
  raceId: string;
  /** /events order: lap descending, then severity descending. */
  events: RaceEvent[];
  focusCode: string | null;
  focusColor: string | null;
}

function formatEvidenceValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Math.round(value * 1000) / 1000);
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) return value.map(formatEvidenceValue).join(", ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${k} ${formatEvidenceValue(v)}`)
      .join(" · ");
  }
  return String(value);
}

function Evidence({ evidence }: { evidence: Record<string, unknown> }) {
  const entries = Object.entries(evidence);
  if (entries.length === 0) return null;
  return (
    <dl data-testid="evidence" className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[11px]">
      {entries.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-zinc-500">{k}</dt>
          <dd className="break-words text-zinc-300">{formatEvidenceValue(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function Analysis({ event }: { event: RaceEvent }) {
  return (
    <div className="flex flex-col gap-1.5 text-sm">
      {(["what", "why", "next"] as const).map((k) => (
        <p key={k}>
          <span className="mr-2 text-[10px] font-bold tracking-wider text-zinc-500">{k.toUpperCase()}</span>
          {event.analysis[k]}
        </p>
      ))}
      <Evidence evidence={event.evidence} />
    </div>
  );
}

function TypeTag({ type }: { type: string }) {
  return (
    <span className="text-[10px] font-bold tracking-wider" style={{ color: eventTypeColor(type) }}>
      {eventTypeLabel(type)}
    </span>
  );
}

function highlightStyle(on: boolean, color: string | null): React.CSSProperties | undefined {
  return on && color ? { boxShadow: `inset 3px 0 0 ${color}`, backgroundColor: `${color}14` } : undefined;
}

function PrimaryCard({ raceId, event, highlighted, focusColor }: {
  raceId: string;
  event: RaceEvent;
  highlighted: boolean;
  focusColor: string | null;
}) {
  const driver = event.drivers[0];
  const wantsStrategy = STRATEGY_EVENT_TYPES.has(event.type) && driver !== undefined;
  const strategyKey = wantsStrategy ? `${raceId}|${event.lap}|${driver}` : null;
  const strategy = useKeyedFetch<StrategyResponse>(strategyKey, (signal) =>
    api.strategy(raceId, event.lap, driver, signal),
  );
  const shown =
    strategy.value && strategy.value.race_id === raceId && strategy.value.driver === driver && strategy.value.lap === event.lap
      ? strategy.value
      : null;
  const severity = Math.max(0, Math.min(100, event.severity));

  return (
    <article
      data-testid="primary-event"
      data-event-id={event.id}
      data-highlight={highlighted || undefined}
      className="flex flex-col gap-2 rounded-md border border-zinc-800 p-3"
      style={highlightStyle(highlighted, focusColor)}
    >
      <div className="flex items-center gap-3 text-xs">
        <TypeTag type={event.type} />
        <span className="text-zinc-400 tabular-nums">LAP {event.lap}</span>
        <span className="font-bold">{event.drivers.join(" · ")}</span>
        <div className="ml-auto flex items-center gap-2" title={`Severity ${Math.round(severity)}`}>
          <div className="h-1.5 w-24 rounded bg-zinc-800">
            <div
              data-testid="severity-bar"
              className="h-full rounded"
              style={{ width: `${severity}%`, backgroundColor: eventTypeColor(event.type) }}
            />
          </div>
          <span className="w-6 text-right text-zinc-500 tabular-nums">{Math.round(severity)}</span>
        </div>
      </div>
      <h2 className="text-lg font-bold">{event.title}</h2>
      <Analysis event={event} />
      {wantsStrategy && (
        <StrategyTable
          response={shown}
          loading={strategy.loadingKey === strategyKey}
          error={strategy.errorKey === strategyKey ? strategy.error : null}
        />
      )}
    </article>
  );
}

export function IntelligencePanel({ raceId, events, focusCode, focusColor }: IntelligencePanelProps) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());
  if (events.length === 0) {
    return (
      <p role="status" className="p-4 text-sm text-zinc-400">
        {NO_EVENTS}
      </p>
    );
  }
  const [primary, ...history] = events;
  const involves = (e: RaceEvent) => focusCode !== null && e.drivers.includes(focusCode);
  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="flex flex-col gap-3 p-3">
      <PrimaryCard raceId={raceId} event={primary} highlighted={involves(primary)} focusColor={focusColor} />
      {history.length > 0 && (
        <section aria-label="Event history">
          <h3 className="mb-1 text-[10px] tracking-wider text-zinc-500">EVENT HISTORY</h3>
          <ul data-testid="event-history" className="flex flex-col">
            {history.map((e) => {
              const open = expanded.has(e.id);
              const highlighted = involves(e);
              return (
                <li
                  key={e.id}
                  data-testid="history-row"
                  data-event-id={e.id}
                  data-highlight={highlighted || undefined}
                  className="border-t border-zinc-800/60"
                  style={highlightStyle(highlighted, focusColor)}
                >
                  <button
                    type="button"
                    aria-expanded={open}
                    className="flex w-full items-center gap-3 px-2 py-1 text-left text-xs hover:bg-zinc-900"
                    onClick={() => toggle(e.id)}
                  >
                    <span className="w-10 text-zinc-500 tabular-nums">L{e.lap}</span>
                    <span className="w-24">
                      <TypeTag type={e.type} />
                    </span>
                    <span className="truncate">{e.title}</span>
                  </button>
                  {open && (
                    <div data-testid="history-analysis" className="px-2 pt-1 pb-2 pl-15">
                      <Analysis event={e} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
