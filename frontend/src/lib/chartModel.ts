import type { DriverState, LapRow } from "../api/types";
import type { PredictionHistory } from "../hooks/usePredictionHistory";

export interface ChartSeries {
  code: string;
  color: string;
  role: "focus" | "ahead" | "behind";
  strokeWidth: number;
  opacity: number;
  /** Dots mark a teammate neighbour, whose line shares the focus driver's colour. */
  dots: boolean;
  /** Row key of the driver's predicted lap time (dashed line). */
  predKey: string;
}

/** A plotted driver's pit-in lap, drawn as "P" in the driver's line colour. */
export interface PitMarker {
  lap: number;
  code: string;
  color: string;
}

export type NeutralisedLabel = "RED" | "SC" | "VSC";

/** A lap with a red flag, safety car, or virtual safety car in any driver's row. */
export interface NeutralisedLap {
  lap: number;
  label: NeutralisedLabel;
  /** First lap of a run of consecutive laps with the same label: the only one that shows it. */
  showLabel: boolean;
}

export interface ChartModel {
  lap: number;
  series: ChartSeries[];
  /** One row per lap 1..lap: { lap, [code]: seconds | null, [predKey]: seconds | null }. */
  rows: Record<string, number | null>[];
  domain: [number, number] | null;
  /** At least one predicted value is plotted. */
  hasPredictions: boolean;
  pitMarkers: PitMarker[];
  neutralised: NeutralisedLap[];
}

/** track_status codes (race-data-replay): 5 red flag, 4 safety car, 6 virtual safety car, by priority. */
const NEUTRALISED: [string, NeutralisedLabel][] = [
  ["5", "RED"],
  ["4", "SC"],
  ["6", "VSC"],
];
const NEUTRALISED_CODES = new Set(NEUTRALISED.map(([code]) => code));

/** Lap 1, pit-in and pit-out laps, and SC / VSC / red-flag laps are left off the solid lines. */
function isRacingLap(r: LapRow): boolean {
  return r.lap > 1 && !r.pit_in && !r.pit_out && !(r.track_status != null && NEUTRALISED_CODES.has(r.track_status));
}

/**
 * Focus driver plus the cars directly ahead and behind at `lap`, with their
 * actual lap times for laps 1..lap only. Null lap times and non-racing laps
 * stay null (gaps); pit stops and neutralised laps are returned as markers.
 * Chart lap k (k >= 2) also gets the lap time predicted at lap k-1.
 */
export function chartModel(
  drivers: DriverState[],
  laps: LapRow[],
  focusCode: string | null,
  lap: number,
  predicted: PredictionHistory = new Map(),
): ChartModel {
  const focus = drivers.find((d) => d.code === focusCode);
  if (!focus) return { lap, series: [], rows: [], domain: null, hasPredictions: false, pitMarkers: [], neutralised: [] };

  const at = (position: number) => drivers.find((d) => d.position === position);
  const picked: [DriverState, ChartSeries["role"]][] = [];
  const ahead = at(focus.position - 1);
  const behind = at(focus.position + 1);
  if (ahead) picked.push([ahead, "ahead"]);
  picked.push([focus, "focus"]);
  if (behind) picked.push([behind, "behind"]);

  const series: ChartSeries[] = picked.map(([d, role]) => ({
    code: d.code,
    color: d.team_color,
    role,
    strokeWidth: role === "focus" ? 3 : 1.5,
    opacity: role === "focus" ? 1 : 0.75,
    dots: role !== "focus" && d.team === focus.team,
    predKey: `${d.code}:pred`,
  }));

  const codes = new Set(series.map((s) => s.code));
  const rows: Record<string, number | null>[] = [];
  let hasPredictions = false;
  for (let n = 1; n <= lap; n++) {
    const row: Record<string, number | null> = { lap: n };
    const made = n >= 2 ? predicted.get(n - 1) : undefined;
    for (const s of series) {
      row[s.code] = null;
      const value = made?.[s.code] ?? null;
      row[s.predKey] = value;
      if (value !== null) hasPredictions = true;
    }
    rows.push(row);
  }
  const colorOf = new Map(series.map((s) => [s.code, s.color]));
  const order = new Map(series.map((s, i) => [s.code, i]));
  const times: number[] = [];
  const pitMarkers: PitMarker[] = [];
  const statusesByLap = new Map<number, Set<string>>();
  for (const r of laps) {
    if (r.lap < 1 || r.lap > lap) continue;
    if (r.track_status != null) {
      const seen = statusesByLap.get(r.lap) ?? new Set<string>();
      seen.add(r.track_status);
      statusesByLap.set(r.lap, seen);
    }
    if (!codes.has(r.driver)) continue;
    if (r.pit_in) pitMarkers.push({ lap: r.lap, code: r.driver, color: colorOf.get(r.driver)! });
    if (!isRacingLap(r)) continue;
    rows[r.lap - 1][r.driver] = r.lap_time_s;
    if (r.lap_time_s != null) times.push(r.lap_time_s);
  }
  pitMarkers.sort((a, b) => a.lap - b.lap || order.get(a.code)! - order.get(b.code)!);

  const neutralised: NeutralisedLap[] = [];
  for (const [n, seen] of [...statusesByLap].sort(([a], [b]) => a - b)) {
    const hit = NEUTRALISED.find(([code]) => seen.has(code));
    if (!hit) continue;
    const prev = neutralised.at(-1);
    const continues = prev !== undefined && prev.lap === n - 1 && prev.label === hit[1];
    neutralised.push({ lap: n, label: hit[1], showLabel: !continues });
  }

  return { lap, series, rows, domain: timeDomain(times), hasPredictions, pitMarkers, neutralised };
}

/**
 * Y range around the plotted (racing) laps: from just under the fastest lap to
 * 3 s above the median. Non-racing laps never reach this list, so their
 * spikes cannot stretch the axis; a very slow racing or predicted lap can
 * still run off the top.
 */
function timeDomain(times: number[]): [number, number] | null {
  if (times.length === 0) return null;
  const sorted = [...times].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  return [Math.floor(sorted[0] - 0.5), Math.ceil(Math.max(median + 3, sorted[0] + 2))];
}
