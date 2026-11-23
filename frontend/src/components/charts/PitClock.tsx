import { fetchRejoin } from "../../api/client";
import type { RejoinResponse, RejoinSlot } from "../../api/types";
import { colorOf } from "./common";
import { ChartBody, type ChartContext, ChartMessage, useChartData } from "./useChartData";

export const PITCLOCK_TITLE = "Pit clock";
export const SNAPSHOT_NOTE = "Snapshot: assumes no other car pits this lap";

const CENTER = 100;
const RADIUS = 78;

/** Clockwise angle from the top, in degrees, of a gap on a clock whose full turn is one lap. */
export function clockAngle(gapS: number, lapLengthS: number): number {
  if (!(lapLengthS > 0)) return 0;
  const wrapped = ((gapS % lapLengthS) + lapLengthS) % lapLengthS;
  return (wrapped / lapLengthS) * 360;
}

function point(angleDeg: number, radius = RADIUS): { x: number; y: number } {
  const t = (angleDeg * Math.PI) / 180;
  return { x: CENTER + radius * Math.sin(t), y: CENTER - radius * Math.cos(t) };
}

/** "Pit now: rejoin P7, 1.1 s behind RUS, 0.6 s ahead of HAM" (parts for a missing car left out). */
export function rejoinText(slot: RejoinSlot): string {
  const parts = [`Pit now: rejoin P${slot.position}`];
  if (slot.ahead !== null && slot.ahead_gap_s !== null) parts.push(`${slot.ahead_gap_s.toFixed(1)} s behind ${slot.ahead}`);
  if (slot.behind !== null && slot.behind_gap_s !== null) parts.push(`${slot.behind_gap_s.toFixed(1)} s ahead of ${slot.behind}`);
  return parts.join(", ");
}

export function lappedLabel(lapsBehind: number): string | null {
  return lapsBehind >= 1 ? `+${lapsBehind}L` : null;
}

interface ViewProps {
  data: RejoinResponse;
  code: string;
  teamColors: Record<string, string | null | undefined>;
}

export function PitClockView({ data, code, teamColors }: ViewProps) {
  if (data.rejoin === null) return <ChartMessage text={`${code} has no gap yet`} />;
  const lapLength = data.lap_length_s;
  if (lapLength === null) return <ChartMessage text="No laps yet" />;
  const ghost = point(clockAngle(data.rejoin.gap_to_leader_s, lapLength));
  return (
    <div className="flex h-full flex-col items-center gap-1 p-2 text-xs">
      <svg viewBox="0 0 200 200" className="h-full max-h-64 min-h-0 w-full" role="img" aria-label="Pit clock">
        <circle cx={CENTER} cy={CENTER} r={RADIUS} fill="none" stroke="#3f3f46" strokeWidth={1.5} />
        <line x1={CENTER} y1={CENTER - RADIUS - 6} x2={CENTER} y2={CENTER - RADIUS + 6} stroke="#71717a" />
        {data.cars.map((car) => {
          const p = point(clockAngle(car.gap_to_leader_s, lapLength));
          const label = point(clockAngle(car.gap_to_leader_s, lapLength), RADIUS - 14);
          const own = car.code === code;
          const lapped = lappedLabel(car.laps_behind_leader);
          return (
            <g key={car.code} data-testid={`clock-car-${car.code}`} data-own={own ? "true" : undefined}>
              {own && <circle cx={p.x} cy={p.y} r={7} fill="none" stroke="#fafafa" strokeWidth={1.5} />}
              <circle cx={p.x} cy={p.y} r={4} fill={colorOf(teamColors, car.code)} />
              <text x={label.x} y={label.y} fontSize={7} fill="#d4d4d8" textAnchor="middle" dominantBaseline="middle">
                {car.code}
                {lapped && ` ${lapped}`}
              </text>
            </g>
          );
        })}
        <circle
          data-testid="clock-rejoin"
          cx={ghost.x}
          cy={ghost.y}
          r={6}
          fill="none"
          stroke={colorOf(teamColors, code)}
          strokeWidth={2}
          strokeDasharray="2 2"
        />
      </svg>
      <p data-testid="rejoin-text" className="text-center text-zinc-100">
        {rejoinText(data.rejoin)}
      </p>
      <p className="text-zinc-400">Pit loss {data.pit_loss_s.toFixed(1)} s</p>
      <p className="text-[10px] text-zinc-500">{SNAPSHOT_NOTE}</p>
    </div>
  );
}

export function PitClock({ ctx, code }: { ctx: ChartContext; code: string | null }) {
  const state = useChartData(ctx, "lap", code === null ? null : [code], (signal) =>
    fetchRejoin(ctx.raceId, ctx.lap, code ?? "", signal),
  );
  const teamColors = Object.fromEntries(ctx.drivers.map((d) => [d.code, d.team_color]));
  if (code === null) return null;
  return (
    <ChartBody title={PITCLOCK_TITLE} state={state}>
      {(data) => <PitClockView data={data} code={code} teamColors={teamColors} />}
    </ChartBody>
  );
}
