// Display formats from specs/race-overview "formatted fields". `null` means
// "show the dash icon"; callers render <Dash /> for it.

export function formatPosition(position: number | null | undefined): string | null {
  if (position == null) return null;
  return String(position).padStart(2, "0");
}

export function formatGap(d: {
  position: number;
  gap_to_leader_s: number | null;
  laps_behind_leader: number;
}): string | null {
  if (d.position === 1) return "LEADER";
  if (d.laps_behind_leader > 0) return `+${d.laps_behind_leader} LAP`;
  if (d.gap_to_leader_s == null) return null;
  return `+${d.gap_to_leader_s.toFixed(3)}`;
}

/** 96.512 → "1:36.512". */
export function formatLapTime(seconds: number | null | undefined): string | null {
  if (seconds == null || !Number.isFinite(seconds)) return null;
  const millis = Math.round(seconds * 1000);
  const minutes = Math.floor(millis / 60000);
  const rest = (millis - minutes * 60000) / 1000;
  return `${minutes}:${rest.toFixed(3).padStart(6, "0")}`;
}

/** Race time for strategy tables: 3830.998 → "1:03:50.998". */
export function formatRaceTime(seconds: number | null | undefined): string | null {
  if (seconds == null || !Number.isFinite(seconds)) return null;
  const millis = Math.round(seconds * 1000);
  const hours = Math.floor(millis / 3600000);
  const minutes = Math.floor((millis - hours * 3600000) / 60000);
  const rest = (millis - hours * 3600000 - minutes * 60000) / 1000;
  const mmss = `${String(minutes).padStart(2, "0")}:${rest.toFixed(3).padStart(6, "0")}`;
  return hours > 0 ? `${hours}:${mmss}` : mmss;
}

/** 0.082 → "+0.082/lap". */
export function formatDeg(sPerLap: number | null | undefined): string | null {
  if (sPerLap == null || !Number.isFinite(sPerLap)) return null;
  const sign = sPerLap < 0 ? "-" : "+";
  return `${sign}${Math.abs(sPerLap).toFixed(3)}/lap`;
}

/** Whole percentage; values below 0.5% show as "<1%". */
export function formatPct(p: number | null | undefined): string | null {
  if (p == null || !Number.isFinite(p)) return null;
  if (p < 0.005) return "<1%";
  return `${Math.round(p * 100)}%`;
}

/** 4.6 → "P4.6"; whole numbers drop the decimal ("P3"). */
export function formatExpectedPosition(p: number | null | undefined): string | null {
  if (p == null || !Number.isFinite(p)) return null;
  const rounded = Math.round(p * 10) / 10;
  return Number.isInteger(rounded) ? `P${rounded}` : `P${rounded.toFixed(1)}`;
}
