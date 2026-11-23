import { type ReactNode, useRef } from "react";
import type { DriverState } from "../../api/types";
import { useKeyedFetch } from "../../hooks/useKeyedFetch";
import { refreshesAt } from "../FocusPanel";

/** What every chart widget knows about the replay ("One chart component per type"). */
export interface ChartContext {
  raceId: string;
  lap: number;
  totalLaps: number;
  playing: boolean;
  focusCode: string | null;
  /** Running order at the lap (state drivers). */
  drivers: DriverState[];
}

/**
 * "lap": request at every lap. "refresh": request when paused, and during
 * playback only on laps divisible by 5 (the focus panel schedule), keeping the
 * last response in between ("Request schedule per widget").
 */
export type ChartSchedule = "lap" | "refresh";

export interface ChartData<T> {
  data: T | null;
  /** The latest request for this widget failed. */
  error: boolean;
}

/**
 * Fetches a chart response for the replay lap. `parts` identifies the request
 * besides race and lap (e.g. the driver); null skips it (no driver yet).
 * Responses from another race are never returned.
 */
export function useChartData<T>(
  ctx: Pick<ChartContext, "raceId" | "lap" | "playing">,
  schedule: ChartSchedule,
  parts: (string | number)[] | null,
  fetcher: (signal: AbortSignal) => Promise<T>,
): ChartData<T> {
  const due = schedule === "lap" || refreshesAt(ctx.lap, ctx.playing);
  const prefix = parts === null ? null : [ctx.raceId, ...parts].join("|");
  const key = prefix !== null && due ? `${prefix}|${ctx.lap}` : null;
  // The newest request sent for this widget; a skipped lap (null key) keeps it.
  const latest = useRef<string | null>(null);
  if (key !== null) latest.current = key;
  if (prefix === null) latest.current = null;
  const result = useKeyedFetch<T>(key, fetcher);
  const ours = (k: string | null) => prefix !== null && k !== null && k.startsWith(`${prefix}|`);
  return {
    data: ours(result.valueKey) ? result.value : null,
    error: result.errorKey !== null && result.errorKey === latest.current,
  };
}

interface ChartBodyProps<T> {
  title: string;
  state: ChartData<T>;
  children: (data: T) => ReactNode;
}

/** "Loading..." before the first response, "Could not load <title>" after a failure. */
export function ChartBody<T>({ title, state, children }: ChartBodyProps<T>) {
  if (state.error) return <ChartMessage text={`Could not load ${title}`} />;
  if (state.data === null) return <ChartMessage text="Loading..." />;
  return <>{children(state.data)}</>;
}

export function ChartMessage({ text }: { text: string }) {
  return (
    <p data-testid="chart-message" className="px-3 py-2 text-xs text-zinc-500">
      {text}
    </p>
  );
}
