import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";
import { fetchTrace } from "../../api/client";
import type { TraceResponse } from "../../api/types";
import { formatLapTime } from "../../lib/format";
import { ChartArea, ChartColumn, type ChartSize, colorOf, GRID_STROKE, TICK, TOOLTIP_STYLE } from "./common";
import { ChartBody, type ChartContext, ChartMessage, useChartData } from "./useChartData";

export const TRACE_TITLE = "Race trace";

export interface TraceSeries {
  code: string;
  color: string;
  strokeWidth: number;
  opacity: number;
}

export interface TraceModel {
  /** One row per lap: { lap, [code]: delta_s }. */
  rows: Record<string, number>[];
  series: TraceSeries[];
}

/** Rows by lap and one series per driver; the focus driver drawn thicker and at full opacity. */
export function traceModel(data: TraceResponse, focusCode: string | null): TraceModel {
  const byLap = new Map<number, Record<string, number>>();
  for (const d of data.drivers) {
    for (const p of d.points) {
      const row = byLap.get(p.lap) ?? { lap: p.lap };
      row[d.code] = p.delta_s;
      byLap.set(p.lap, row);
    }
  }
  const colors = Object.fromEntries(data.drivers.map((d) => [d.code, d.team_color]));
  return {
    rows: [...byLap.values()].sort((a, b) => a.lap - b.lap),
    series: data.drivers.map((d) => ({
      code: d.code,
      color: colorOf(colors, d.code),
      strokeWidth: d.code === focusCode ? 3 : 1.25,
      opacity: d.code === focusCode ? 1 : 0.45,
    })),
  };
}

export function traceCaption(referenceLapS: number): string {
  return `Reference pace ${formatLapTime(referenceLapS)}`;
}

interface ViewProps {
  data: TraceResponse;
  focusCode: string | null;
  size?: ChartSize;
}

export function RaceTraceView({ data, focusCode, size }: ViewProps) {
  const model = useMemo(() => traceModel(data, focusCode), [data, focusCode]);
  if (data.reference_lap_s === null) return <ChartMessage text="No laps yet" />;
  // Focus line drawn last so it sits on top.
  const ordered = [...model.series].sort((a, b) => a.strokeWidth - b.strokeWidth);
  return (
    <ChartColumn caption={<span>{traceCaption(data.reference_lap_s)} · above zero = ahead</span>}>
      <ChartArea
        size={size}
        chart={(s) => (
          <LineChart data={model.rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }} {...s}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis dataKey="lap" type="number" domain={[1, Math.max(data.lap, 2)]} tick={TICK} />
            <YAxis width={44} tick={TICK} tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(0)}`} />
            <ReferenceLine y={0} stroke="#52525b" />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelFormatter={(l) => `Lap ${l}`}
              formatter={(v) => (typeof v === "number" ? `${v > 0 ? "+" : ""}${v.toFixed(3)} s` : "—")}
            />
            {ordered.map((s) => (
              <Line
                key={s.code}
                dataKey={s.code}
                name={s.code}
                type="linear"
                stroke={s.color}
                strokeWidth={s.strokeWidth}
                strokeOpacity={s.opacity}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        )}
      />
    </ChartColumn>
  );
}

export function RaceTrace({ ctx, size }: { ctx: ChartContext; size?: ChartSize }) {
  const state = useChartData(ctx, "lap", [], (signal) => fetchTrace(ctx.raceId, ctx.lap, signal));
  return (
    <ChartBody title={TRACE_TITLE} state={state}>
      {(data) => <RaceTraceView data={data} focusCode={ctx.focusCode} size={size} />}
    </ChartBody>
  );
}
