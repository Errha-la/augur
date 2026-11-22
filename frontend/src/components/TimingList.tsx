import { MotionConfig, motion } from "motion/react";
import { useEffect, useMemo, useRef } from "react";
import type { DriverPositions, DriverPrediction, DriverState, LapRow } from "../api/types";
import { formatDeg, formatGap, formatLapTime, formatPct, formatPosition } from "../lib/format";
import { lastLapMarks } from "../lib/laps";
import { compoundColor, compoundLetter } from "../lib/theme";
import { Dash, OrDash } from "./Dash";

interface TimingListProps {
  lap: number;
  drivers: DriverState[];
  laps: LapRow[];
  predictions: DriverPrediction[];
  positions: DriverPositions[];
  focusCode: string | null;
  onFocus: (code: string) => void;
}

const MARK_CLASS = { fastest: "text-purple-400", "personal-best": "text-emerald-400" } as const;

/** Row slide when the order changes: the race-dashboard design's ease and duration. */
export const ROW_TRANSITION = { duration: 0.75, ease: [0.2, 1, 0.2, 1] as [number, number, number, number] };

export function TimingList({ lap, drivers, laps, predictions, positions, focusCode, onFocus }: TimingListProps) {
  const ordered = useMemo(() => [...drivers].sort((a, b) => a.position - b.position), [drivers]);
  // Positions shown last render: rows whose position changed are the ones that slide.
  const shown = useRef<Map<string, number> | null>(null);
  const previous = shown.current;
  useEffect(() => {
    shown.current = new Map(drivers.map((d) => [d.code, d.position]));
  }, [drivers]);
  const marks = useMemo(() => lastLapMarks(laps, lap), [laps, lap]);
  const predByCode = useMemo(() => new Map(predictions.map((p) => [p.code, p])), [predictions]);
  const posByCode = useMemo(() => new Map(positions.map((p) => [p.code, p])), [positions]);

  return (
    <MotionConfig reducedMotion="user">
    <table className="w-full border-collapse text-sm tabular-nums">
      <thead className="sticky top-0 bg-card text-left text-[10px] tracking-wider text-zinc-500">
        <tr>
          <th className="w-1.5 p-0" aria-label="Team" />
          <th className="px-2 py-1">POS</th>
          <th className="px-1 py-1">DRIVER</th>
          <th className="px-1 py-1">TYRE</th>
          <th className="px-2 py-1 text-right">GAP</th>
          <th className="px-2 py-1 text-right">LAST</th>
          <th className="px-2 py-1 text-right">NEXT</th>
          <th className="px-2 py-1 text-right">DEG</th>
          <th className="px-2 py-1 text-right">WIN</th>
          <th className="px-2 py-1 text-right">PODIUM</th>
        </tr>
      </thead>
      <tbody>
        {ordered.map((d) => {
          const pred = predByCode.get(d.code);
          const pos = posByCode.get(d.code);
          // Colour only the time it was computed for, never a different lap's time.
          const info = marks.get(d.code);
          const mark = info && d.last_lap_time_s != null && info.time === d.last_lap_time_s ? info.mark : null;
          const letter = compoundLetter(d.compound);
          const podium = pos?.p_podium ?? null;
          const focused = d.code === focusCode;
          const before = previous?.get(d.code);
          const moved = before !== undefined && before !== d.position;
          return (
            <motion.tr
              key={d.code}
              layout="position"
              transition={ROW_TRANSITION}
              data-moved={moved || undefined}
              data-testid={`row-${d.code}`}
              data-focus={focused || undefined}
              aria-selected={focused}
              tabIndex={0}
              onClick={() => onFocus(d.code)}
              onKeyDown={(e) => {
                if (e.key === "Enter") onFocus(d.code);
              }}
              className="cursor-pointer border-t border-zinc-800/60 hover:bg-zinc-900"
              style={focused ? { backgroundColor: `${d.team_color}24`, outline: `1px solid ${d.team_color}` } : undefined}
            >
              <td className="w-1.5 p-0" style={{ backgroundColor: d.team_color }} />
              <td data-field="position" className="px-2 py-1 text-2xl font-bold text-zinc-400">
                <OrDash text={formatPosition(d.position)} />
              </td>
              <td data-field="code" className="px-1 py-1 text-2xl font-bold">
                {d.code}
              </td>
              <td data-field="tyre" className="px-1 py-1 whitespace-nowrap">
                {letter ? (
                  <span data-field="compound" className="text-2xl" style={{ color: compoundColor(d.compound) }}>
                    {letter}
                  </span>
                ) : (
                  <Dash />
                )}
                <span className="mx-1.5 inline-block h-5 w-px bg-zinc-800 align-middle" />
                <span data-field="tyre-age" className="text-zinc-600">
                  <OrDash text={d.tyre_age_laps == null ? null : String(d.tyre_age_laps)} />
                </span>
              </td>
              <td data-field="gap" className="px-2 py-1 text-right">
                <OrDash text={formatGap(d)} />
              </td>
              <td data-field="last" data-mark={mark ?? undefined} className={`px-2 py-1 text-right ${mark ? MARK_CLASS[mark] : ""}`}>
                <OrDash text={formatLapTime(d.last_lap_time_s)} />
              </td>
              <td data-field="next" className="px-2 py-1 text-right text-zinc-400">
                <OrDash text={formatLapTime(pred?.predicted_next_lap_s)} />
              </td>
              <td data-field="deg" className="px-2 py-1 text-right whitespace-nowrap text-zinc-400">
                <OrDash text={formatDeg(pred?.deg_s_per_lap)} />
                {pred?.cliff && (
                  <span className="ml-1 rounded bg-flag-red/20 px-1 text-[10px] font-bold text-flag-red">CLIFF</span>
                )}
              </td>
              <td data-field="win" className="px-2 py-1 text-right">
                <OrDash text={formatPct(pos?.p_win)} />
              </td>
              <td data-field="podium" className="px-2 py-1 text-right">
                <OrDash text={formatPct(podium)} />
                <div className="mt-0.5 h-0.5 w-full rounded bg-zinc-800">
                  <div
                    data-testid="podium-bar"
                    className="h-full rounded bg-zinc-300"
                    style={{ width: `${Math.round((podium ?? 0) * 100)}%` }}
                  />
                </div>
              </td>
            </motion.tr>
          );
        })}
      </tbody>
    </table>
    </MotionConfig>
  );
}
