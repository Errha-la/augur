import { useMemo } from "react";
import { Area, CartesianGrid, ComposedChart, Line, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../../api/client";
import type { PositionsHistoryResponse } from "../../api/types";
import { ChartArea, ChartColumn, type ChartSize, colorOf, GRID_STROKE, TICK, TOOLTIP_STYLE } from "./common";
import { ChartBody, type ChartContext, ChartMessage, useChartData } from "./useChartData";

export const FAN_TITLE = "Position fan";

export interface FanRow {
  lap: number;
  expected: number | null;
  band: [number, number] | null;
}

/** The driver's expected position and p10-p90 band per lap; laps without the driver are left out. */
export function fanRows(data: PositionsHistoryResponse, code: string): FanRow[] {
  const rows: FanRow[] = [];
  for (const l of data.laps) {
    const d = l.drivers.find((x) => x.code === code);
    if (!d) continue;
    const band: [number, number] | null =
      d.position_p10 !== null && d.position_p90 !== null ? [d.position_p10, d.position_p90] : null;
    rows.push({ lap: l.lap, expected: d.expected_position, band });
  }
  return rows;
}

interface ViewProps {
  data: PositionsHistoryResponse;
  code: string;
  color: string;
  lap: number;
  size?: ChartSize;
}

export function PositionFanView({ data, code, color, lap, size }: ViewProps) {
  const rows = useMemo(() => fanRows(data, code), [data, code]);
  if (!data.analyzed) return <ChartMessage text="Race not analyzed" />;
  const maxPos = Math.max(3, ...rows.map((r) => r.band?.[1] ?? r.expected ?? 1));
  return (
    <ChartColumn caption={<span>{code}: expected position, band P10-P90</span>}>
      <ChartArea
        size={size}
        chart={(s) => (
          <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }} {...s}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis dataKey="lap" type="number" domain={[1, Math.max(lap, 2)]} tick={TICK} />
            {/* P1 at the top. */}
            <YAxis reversed domain={[1, Math.ceil(maxPos)]} allowDecimals={false} width={32} tick={TICK} tickFormatter={(v: number) => `P${v}`} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelFormatter={(l) => `Lap ${l}`}
              formatter={(v) => (Array.isArray(v) ? `P${v[0]}-P${v[1]}` : `P${Number(v).toFixed(1)}`)}
            />
            <Area dataKey="band" name="P10-P90" stroke="none" fill={color} fillOpacity={0.22} isAnimationActive={false} />
            <Line dataKey="expected" name="Expected" stroke={color} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
          </ComposedChart>
        )}
      />
    </ChartColumn>
  );
}

export function PositionFan({ ctx, code, size }: { ctx: ChartContext; code: string | null; size?: ChartSize }) {
  // Same request and schedule as the focus panel's probability history (shared cache).
  const state = useChartData(ctx, "refresh", code === null ? null : ["history"], (signal) =>
    api.positionsHistory(ctx.raceId, ctx.lap, signal),
  );
  const color = colorOf(Object.fromEntries(ctx.drivers.map((d) => [d.code, d.team_color])), code ?? "");
  if (code === null) return null;
  return (
    <ChartBody title={FAN_TITLE} state={state}>
      {(data) => <PositionFanView data={data} code={code} color={color} lap={ctx.lap} size={size} />}
    </ChartBody>
  );
}
