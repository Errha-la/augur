import type { LapRow } from "../api/types";

const DRY = new Set(["SOFT", "MEDIUM", "HARD"]);

/**
 * Clean-lap rule of backend `features.clean_mask`, without its outlier rule:
 * that rule only removes laps slower than the fastest clean lap, so it never
 * changes which lap is fastest.
 */
export function isCleanLap(r: LapRow): boolean {
  return (
    r.lap_time_s != null &&
    r.lap > 1 &&
    !r.pit_in &&
    !r.pit_out &&
    r.track_status === "1" &&
    r.is_accurate &&
    r.compound != null &&
    DRY.has(r.compound)
  );
}

export type LastLapMark = "fastest" | "personal-best" | null;

/**
 * For each driver's latest lap up to `lap`: "fastest" (purple) when it is the
 * fastest clean lap of the race so far, "personal-best" (green) when it is the
 * driver's own fastest lap so far.
 */
export function lastLapMarks(laps: LapRow[], lap: number): Map<string, LastLapMark> {
  let raceBest = Infinity;
  const ownBest = new Map<string, number>();
  const latest = new Map<string, LapRow>();
  for (const r of laps) {
    if (r.lap > lap) continue;
    const prev = latest.get(r.driver);
    if (!prev || r.lap > prev.lap) latest.set(r.driver, r);
    if (r.lap_time_s == null) continue;
    if (isCleanLap(r)) raceBest = Math.min(raceBest, r.lap_time_s);
    ownBest.set(r.driver, Math.min(ownBest.get(r.driver) ?? Infinity, r.lap_time_s));
  }
  const marks = new Map<string, LastLapMark>();
  for (const [driver, r] of latest) {
    let mark: LastLapMark = null;
    if (r.lap_time_s != null) {
      if (isCleanLap(r) && r.lap_time_s <= raceBest) mark = "fastest";
      else if (r.lap_time_s <= (ownBest.get(driver) ?? Infinity)) mark = "personal-best";
    }
    marks.set(driver, mark);
  }
  return marks;
}

export interface Stint {
  stint: number;
  compound: string | null;
  startLap: number;
  laps: number;
}

/** One entry per stint of `driver` up to `lap`, from the per-lap rows. */
export function stintsOf(laps: LapRow[], driver: string, lap: number): Stint[] {
  const rows = laps.filter((r) => r.driver === driver && r.lap <= lap).sort((a, b) => a.lap - b.lap);
  const stints: Stint[] = [];
  for (const r of rows) {
    const last = stints.at(-1);
    const key = r.stint ?? last?.stint ?? 1;
    if (last && last.stint === key) {
      last.laps += 1;
      last.compound ??= r.compound;
    } else {
      stints.push({ stint: key, compound: r.compound, startLap: r.lap, laps: 1 });
    }
  }
  return stints;
}
