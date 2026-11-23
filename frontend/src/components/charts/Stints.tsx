import { fetchStints } from "../../api/client";
import type { Stint, StintsResponse } from "../../api/types";
import { compoundColor, compoundLetter } from "../../lib/theme";
import { ChartBody, type ChartContext, ChartMessage, useChartData } from "./useChartData";

export const STINTS_TITLE = "Tyre stints";
/** Shortest segment (laps) that shows its compound letter. */
export const LETTER_MIN_LAPS = 4;

export interface Segment {
  stint: number;
  compound: Stint["compound"];
  startLap: number;
  endLap: number;
  /** Percent of the 1..totalLaps axis. */
  left: number;
  width: number;
  letter: string | null;
}

export function segments(stints: Stint[], totalLaps: number): Segment[] {
  const total = Math.max(totalLaps, 1);
  return stints.map((s) => {
    const laps = s.end_lap - s.start_lap + 1;
    return {
      stint: s.stint,
      compound: s.compound,
      startLap: s.start_lap,
      endLap: s.end_lap,
      left: ((s.start_lap - 1) / total) * 100,
      width: (laps / total) * 100,
      letter: laps >= LETTER_MIN_LAPS ? compoundLetter(s.compound) : null,
    };
  });
}

interface ViewProps {
  data: StintsResponse;
  totalLaps: number;
  focusCode: string | null;
}

export function StintsView({ data, totalLaps, focusCode }: ViewProps) {
  if (data.drivers.every((d) => d.stints.length === 0)) return <ChartMessage text="No laps yet" />;
  return (
    <div className="flex flex-col gap-0.5 p-2 text-[11px]">
      {data.drivers.map((d) => (
        <div
          key={d.code}
          data-testid={`stints-${d.code}`}
          data-focus={d.code === focusCode ? "true" : undefined}
          className={`flex items-center gap-2 rounded px-1 ${d.code === focusCode ? "bg-zinc-800 font-bold text-zinc-100" : "text-zinc-400"}`}
        >
          <span className="w-9 shrink-0">{d.code}</span>
          <div className="relative h-3 flex-1 rounded-sm bg-zinc-900">
            {segments(d.stints, totalLaps).map((s) => (
              <div
                key={s.stint}
                data-testid="stint-segment"
                data-compound={s.compound ?? ""}
                data-laps={`${s.startLap}-${s.endLap}`}
                title={`${s.compound ?? "Unknown"} laps ${s.startLap}-${s.endLap}`}
                className="absolute top-0 flex h-full items-center justify-center overflow-hidden rounded-sm border-r border-zinc-950 text-[9px] font-bold text-zinc-950"
                style={{ left: `${s.left}%`, width: `${s.width}%`, backgroundColor: compoundColor(s.compound) }}
              >
                {s.letter}
              </div>
            ))}
          </div>
        </div>
      ))}
      <div className="flex justify-between pl-11 text-[10px] text-zinc-600">
        <span>Lap 1</span>
        <span>Lap {totalLaps}</span>
      </div>
    </div>
  );
}

export function Stints({ ctx }: { ctx: ChartContext }) {
  const state = useChartData(ctx, "lap", [], (signal) => fetchStints(ctx.raceId, ctx.lap, signal));
  return (
    <ChartBody title={STINTS_TITLE} state={state}>
      {(data) => <StintsView data={data} totalLaps={ctx.totalLaps} focusCode={ctx.focusCode} />}
    </ChartBody>
  );
}
