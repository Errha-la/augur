import { type ReactNode, useEffect, useRef } from "react";
import { api, fetchDegradation, fetchPitWindow, fetchStints, fetchTrace } from "../../api/client";
import type {
  DegradationCompound,
  DegradationResponse,
  LapRow,
  LinkChart,
  NumberLink,
  PitWindowResponse,
  PositionsHistoryResponse,
  RaceState,
  StintsResponse,
  TraceResponse,
} from "../../api/types";
import { useKeyedFetch } from "../../hooks/useKeyedFetch";
import { DEGRADATION_TITLE, DegradationView } from "../charts/Degradation";
import { PITWINDOW_TITLE, PitWindowView } from "../charts/PitWindow";
import { FAN_TITLE, PositionFanView } from "../charts/PositionFan";
import { RaceTraceView, TRACE_TITLE } from "../charts/RaceTrace";
import { STINTS_TITLE, StintsView } from "../charts/Stints";
import { colorOf } from "../charts/common";
import { ChartMessage } from "../charts/useChartData";
import { LapChart } from "../LapChart";

export const LAPTIMES_TITLE = "Lap times";
export const POPOVER_LOADING = "Loading...";
export const POPOVER_FAILED = "Could not load chart";

export const LINK_CHART_TITLES: Record<LinkChart, string> = {
  degradation: DEGRADATION_TITLE,
  laptimes: LAPTIMES_TITLE,
  trace: TRACE_TITLE,
  stints: STINTS_TITLE,
  pitwindow: PITWINDOW_TITLE,
  positions: FAN_TITLE,
};

/** Popover chart size (the dialog is about 320 x 200 px). */
const CHART_SIZE = { width: 296, height: 140 };
const POPOVER_WIDTH = 320;
const POPOVER_HEIGHT = 230;

/** "Race trace · NOR PIA · lap 20". */
export function popoverTitle(link: NumberLink, lap: number): string {
  return [LINK_CHART_TITLES[link.chart], link.drivers.join(" "), `lap ${lap}`].filter(Boolean).join(" · ");
}

/** Least-squares line through the points, or null with fewer than two distinct tyre ages. */
export function fitPoints(points: DegradationCompound["points"]): DegradationCompound["fit"] {
  const n = points.length;
  if (n < 2) return null;
  const mx = points.reduce((s, p) => s + p.tyre_age, 0) / n;
  const my = points.reduce((s, p) => s + p.fuel_corrected_s, 0) / n;
  const sxx = points.reduce((s, p) => s + (p.tyre_age - mx) ** 2, 0);
  if (sxx === 0) return null;
  const sxy = points.reduce((s, p) => s + (p.tyre_age - mx) * (p.fuel_corrected_s - my), 0);
  const slope = sxy / sxx;
  return { slope_s_per_lap: slope, intercept_s: my - slope * mx, n };
}

/** Only the driver's points per compound, fit lines recomputed from them. */
export function driverDegradation(data: DegradationResponse, code: string): DegradationResponse {
  const compounds = data.compounds
    .map((c) => {
      const points = c.points.filter((p) => p.code === code);
      return { ...c, points, fit: fitPoints(points) };
    })
    .filter((c) => c.points.length > 0);
  return { ...data, compounds };
}

export function onlyTraceDrivers(data: TraceResponse, codes: string[]): TraceResponse {
  return { ...data, drivers: data.drivers.filter((d) => codes.includes(d.code)) };
}

export function onlyStintDrivers(data: StintsResponse, codes: string[]): StintsResponse {
  return { ...data, drivers: data.drivers.filter((d) => codes.includes(d.code)) };
}

interface LapTimes {
  state: RaceState;
  laps: LapRow[];
}

type PopoverData = DegradationResponse | LapTimes | TraceResponse | StintsResponse | PitWindowResponse | PositionsHistoryResponse;

function fetchFor(raceId: string, lap: number, link: NumberLink, signal: AbortSignal): Promise<PopoverData> {
  const driver = link.drivers[0];
  switch (link.chart) {
    case "degradation":
      return fetchDegradation(raceId, lap, signal);
    case "laptimes":
      return Promise.all([api.state(raceId, lap, signal), api.laps(raceId, lap, signal)]).then(([state, laps]) => ({ state, laps }));
    case "trace":
      return fetchTrace(raceId, lap, signal);
    case "stints":
      return fetchStints(raceId, lap, signal);
    case "pitwindow":
      return fetchPitWindow(raceId, lap, driver, signal);
    case "positions":
      return api.positionsHistory(raceId, lap, signal);
  }
}

function caption(link: NumberLink, evidence: Record<string, unknown>): string | null {
  let value: unknown = evidence;
  for (const part of link.field.split(".")) {
    value = value && typeof value === "object" ? (value as Record<string, unknown>)[part] : undefined;
  }
  return typeof value === "number" ? `${link.field} ${value}` : null;
}

function renderChart(
  link: NumberLink,
  data: PopoverData,
  lap: number,
  totalLaps: number,
  teamColors: Record<string, string | null | undefined>,
  evidence: Record<string, unknown>,
): ReactNode {
  const driver = link.drivers[0];
  switch (link.chart) {
    case "degradation": {
      const note = caption(link, evidence);
      return (
        <>
          {note && <p data-testid="popover-caption" className="px-3 pt-1 text-[11px] text-zinc-400">{note}</p>}
          <DegradationView data={driverDegradation(data as DegradationResponse, driver)} focusCode={driver} size={CHART_SIZE} />
        </>
      );
    }
    case "laptimes": {
      const { state, laps } = data as LapTimes;
      return <LapChart lap={lap} drivers={state.drivers} laps={laps} focusCode={driver} size={CHART_SIZE} />;
    }
    case "trace":
      return <RaceTraceView data={onlyTraceDrivers(data as TraceResponse, link.drivers)} focusCode={driver} size={CHART_SIZE} />;
    case "stints":
      return <StintsView data={onlyStintDrivers(data as StintsResponse, link.drivers)} totalLaps={totalLaps} focusCode={driver} />;
    case "pitwindow":
      return <PitWindowView data={data as PitWindowResponse} totalLaps={totalLaps} color={colorOf(teamColors, driver)} size={CHART_SIZE} />;
    case "positions":
      return (
        <PositionFanView
          data={data as PositionsHistoryResponse}
          code={driver}
          color={colorOf(teamColors, driver)}
          lap={lap}
          size={CHART_SIZE}
        />
      );
  }
}

export interface ChartPopoverProps {
  raceId: string;
  /** The event's lap: every chart is requested at it, never at the replay lap. */
  lap: number;
  link: NumberLink;
  evidence: Record<string, unknown>;
  totalLaps: number;
  teamColors: Record<string, string | null | undefined>;
  /** The clicked number; the popover sits under it, and clicks on it are not "outside". */
  anchor: HTMLElement | null;
  onClose: () => void;
}

/** Where the dialog goes: under the anchor, kept inside the viewport (above it near the bottom). */
function placement(anchor: HTMLElement | null): { left: number; top: number } {
  if (!anchor) return { left: 16, top: 16 };
  const r = anchor.getBoundingClientRect();
  const vw = window.innerWidth || POPOVER_WIDTH;
  const vh = window.innerHeight || POPOVER_HEIGHT;
  const left = Math.max(8, Math.min(r.left, vw - POPOVER_WIDTH - 8));
  const below = r.bottom + 4;
  const top = below + POPOVER_HEIGHT > vh && r.top - POPOVER_HEIGHT - 4 >= 0 ? r.top - POPOVER_HEIGHT - 4 : below;
  return { left, top };
}

/** A small dialog with one chart of the link's value at the event's lap. */
export function ChartPopover({ raceId, lap, link, evidence, totalLaps, teamColors, anchor, onClose }: ChartPopoverProps) {
  const root = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const driver = link.drivers[0];
  // Without a driver nothing can be drawn; skip the request.
  const key = driver ? [raceId, link.chart, lap, link.drivers.join(",")].join("|") : null;
  const result = useKeyedFetch<PopoverData>(key, (signal) => fetchFor(raceId, lap, link, signal));

  useEffect(() => {
    const inside = (target: EventTarget | null) =>
      target instanceof Node && (root.current?.contains(target) || anchor?.contains(target));
    const onDown = (e: MouseEvent) => {
      if (!inside(e.target)) onCloseRef.current();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [anchor]);

  const title = popoverTitle(link, lap);
  let body: ReactNode;
  if (key === null || (result.errorKey === key && result.valueKey !== key)) body = <ChartMessage text={POPOVER_FAILED} />;
  else if (result.valueKey !== key || result.value === null) body = <ChartMessage text={POPOVER_LOADING} />;
  else body = renderChart(link, result.value, lap, totalLaps, teamColors, evidence);

  return (
    <div
      ref={root}
      role="dialog"
      aria-label={title}
      data-testid="chart-popover"
      data-chart={link.chart}
      className="fixed z-50 flex w-80 flex-col rounded-md border border-zinc-700 bg-card shadow-xl shadow-black/50"
      style={placement(anchor)}
    >
      <h4 className="truncate border-b border-zinc-800 px-3 py-1.5 text-[11px] font-bold text-zinc-200">{title}</h4>
      <div className="min-h-24">{body}</div>
    </div>
  );
}
