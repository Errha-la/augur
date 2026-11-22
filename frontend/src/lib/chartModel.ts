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

export interface ChartModel {
  lap: number;
  series: ChartSeries[];
  /** One row per lap 1..lap: { lap, [code]: seconds | null, [predKey]: seconds | null }. */
  rows: Record<string, number | null>[];
  domain: [number, number] | null;
  /** At least one predicted value is plotted. */
  hasPredictions: boolean;
}

/**
 * Focus driver plus the cars directly ahead and behind at `lap`, with their
 * actual lap times for laps 1..lap only. Null lap times stay null (gaps).
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
  if (!focus) return { lap, series: [], rows: [], domain: null, hasPredictions: false };

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
  const times: number[] = [];
  for (const r of laps) {
    if (r.lap < 1 || r.lap > lap || !codes.has(r.driver)) continue;
    rows[r.lap - 1][r.driver] = r.lap_time_s;
    if (r.lap_time_s != null) times.push(r.lap_time_s);
  }

  return { lap, series, rows, domain: timeDomain(times), hasPredictions };
}

/**
 * Y range around racing laps: from just under the fastest lap to 3 s above the
 * median, so lap 1, pit and safety-car laps run off the top instead of
 * flattening the lines that matter.
 */
function timeDomain(times: number[]): [number, number] | null {
  if (times.length === 0) return null;
  const sorted = [...times].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  return [Math.floor(sorted[0] - 0.5), Math.ceil(Math.max(median + 3, sorted[0] + 2))];
}
