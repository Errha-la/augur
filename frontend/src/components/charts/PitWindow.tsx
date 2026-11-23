import { useMemo } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";
import { fetchPitWindow } from "../../api/client";
import type { PitWindowResponse } from "../../api/types";
import { ChartArea, ChartColumn, type ChartSize, colorOf, GRID_STROKE, TICK, TOOLTIP_STYLE } from "./common";
import { ChartBody, type ChartContext, ChartMessage, useChartData } from "./useChartData";

export const PITWINDOW_TITLE = "Pit window";
export const GREEN_RACE_CAPTION = "Green race assumed";
export const NO_STOP_LABEL = "No further stop";

export interface PitWindowModel {
  /** One row per pit lap: delta to the best plan and the p10-p90 band on the same scale. */
  rows: { pit_lap: number; delta_s: number; band: [number, number] }[];
  /** delta_s of the no-stop plan, when offered. */
  noStopDelta: number | null;
}

export function pitWindowModel(data: PitWindowResponse): PitWindowModel {
  const rows: PitWindowModel["rows"] = [];
  let noStopDelta: number | null = null;
  for (const p of data.plans) {
    // Every plan's mean minus its delta is the best plan's mean: shift the band by it.
    const offset = p.mean_s - p.delta_s;
    if (p.pit_lap === null) noStopDelta = p.delta_s;
    else rows.push({ pit_lap: p.pit_lap, delta_s: p.delta_s, band: [p.p10_s - offset, p.p90_s - offset] });
  }
  return { rows, noStopDelta };
}

/** Empty plans: no lap left to stop on (N >= total_laps - 2), or too early to simulate. */
export function emptyWindowText(lap: number, totalLaps: number): string {
  return lap >= totalLaps - 2 ? "No pit window left" : "Not enough laps yet";
}

interface ViewProps {
  data: PitWindowResponse;
  totalLaps: number;
  color: string;
  size?: ChartSize;
}

export function PitWindowView({ data, totalLaps, color, size }: ViewProps) {
  const model = useMemo(() => pitWindowModel(data), [data]);
  if (data.plans.length === 0) return <ChartMessage text={emptyWindowText(data.lap, totalLaps)} />;
  return (
    <ChartColumn
      caption={
        <>
          {data.best_pit_lap !== null && (
            <span data-testid="best-pit-lap" className="font-bold text-zinc-100">
              Best: lap {data.best_pit_lap}
            </span>
          )}
          {model.noStopDelta !== null && (
            <span data-testid="no-stop" className="text-zinc-300">
              dashed: {NO_STOP_LABEL} (+{model.noStopDelta.toFixed(1)} s)
            </span>
          )}
          <span>seconds slower than the best plan</span>
          <span className="text-zinc-500">{GREEN_RACE_CAPTION}</span>
        </>
      }
    >
      <ChartArea
        size={size}
        chart={(s) => (
          <ComposedChart data={model.rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }} {...s}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis dataKey="pit_lap" type="number" domain={["dataMin", "dataMax"]} tick={TICK} allowDecimals={false} />
            <YAxis width={40} tick={TICK} tickFormatter={(v: number) => `+${v.toFixed(0)}`} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelFormatter={(l) => `Pit on lap ${l}`}
              formatter={(v) =>
                Array.isArray(v) ? `${Number(v[0]).toFixed(1)} to ${Number(v[1]).toFixed(1)} s` : `+${Number(v).toFixed(1)} s`
              }
            />
            <Area dataKey="band" name="p10-p90" stroke="none" fill={color} fillOpacity={0.18} isAnimationActive={false} />
            <Line dataKey="delta_s" name="Expected" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
            {data.best_pit_lap !== null && <ReferenceLine x={data.best_pit_lap} stroke="#fafafa" strokeDasharray="2 3" />}
            {model.noStopDelta !== null && (
              <ReferenceLine y={model.noStopDelta} stroke="#a1a1aa" strokeDasharray="5 4" label={{ value: NO_STOP_LABEL, fill: "#a1a1aa", fontSize: 10, position: "insideTopRight" }} />
            )}
          </ComposedChart>
        )}
      />
    </ChartColumn>
  );
}

export function PitWindow({ ctx, code, size }: { ctx: ChartContext; code: string | null; size?: ChartSize }) {
  const state = useChartData(ctx, "refresh", code === null ? null : [code], (signal) =>
    fetchPitWindow(ctx.raceId, ctx.lap, code ?? "", signal),
  );
  const color = colorOf(Object.fromEntries(ctx.drivers.map((d) => [d.code, d.team_color])), code ?? "");
  if (code === null) return null;
  return (
    <ChartBody title={PITWINDOW_TITLE} state={state}>
      {(data) => <PitWindowView data={data} totalLaps={ctx.totalLaps} color={color} size={size} />}
    </ChartBody>
  );
}
