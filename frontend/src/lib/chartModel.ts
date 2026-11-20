import type { DriverState, LapRow } from "../api/types";

export interface ChartSeries {
  code: string;
  color: string;
  role: "focus" | "ahead" | "behind";
  strokeWidth: number;
  opacity: number;
  /** Dots mark a teammate neighbour, whose line shares the focus driver's colour. */
  dots: boolean;
}

export interface ChartModel {
  lap: number;
  series: ChartSeries[];
  /** One row per lap 1..lap: { lap, [code]: seconds | null }. */
  rows: Record<string, number | null>[];
  domain: [number, number] | null;
}

/**
 * Focus driver plus the cars directly ahead and behind at `lap`, with their
 * actual lap times for laps 1..lap only. Null lap times stay null (gaps).
 */
export function chartModel(drivers: DriverState[], laps: LapRow[], focusCode: string | null, lap: number): ChartModel {
  const focus = drivers.find((d) => d.code === focusCode);
  if (!focus) return { lap, series: [], rows: [], domain: null };

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
  }));

  const codes = new Set(series.map((s) => s.code));
  const rows: Record<string, number | null>[] = [];
  for (let n = 1; n <= lap; n++) {
    const row: Record<string, number | null> = { lap: n };
    for (const c of codes) row[c] = null;
    rows.push(row);
  }
  const times: number[] = [];
  for (const r of laps) {
    if (r.lap < 1 || r.lap > lap || !codes.has(r.driver)) continue;
    rows[r.lap - 1][r.driver] = r.lap_time_s;
    if (r.lap_time_s != null) times.push(r.lap_time_s);
  }

  return { lap, series, rows, domain: timeDomain(times) };
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
