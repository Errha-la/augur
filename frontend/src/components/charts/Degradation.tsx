import { useMemo } from "react";
import { CartesianGrid, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { fetchDegradation } from "../../api/client";
import type { DegradationCompound, DegradationResponse } from "../../api/types";
import { formatLapTime } from "../../lib/format";
import { compoundColor } from "../../lib/theme";
import { ChartArea, ChartColumn, type ChartSize, GRID_STROKE, TICK, TOOLTIP_STYLE } from "./common";
import { ChartBody, type ChartContext, ChartMessage, useChartData } from "./useChartData";

export const DEGRADATION_TITLE = "Degradation";

/** "SOFT +0.179 s/lap (24)" with a fit, "HARD (3)" without. */
export function legendText(c: DegradationCompound): string {
  if (!c.fit) return `${c.compound} (${c.points.length})`;
  const slope = c.fit.slope_s_per_lap;
  return `${c.compound} ${slope >= 0 ? "+" : ""}${slope.toFixed(3)} s/lap (${c.fit.n})`;
}

/** Two end points of a compound's fit line over its tyre-age range, or none. */
export function fitLine(c: DegradationCompound): { tyre_age: number; fuel_corrected_s: number }[] {
  if (!c.fit || c.points.length === 0) return [];
  const ages = c.points.map((p) => p.tyre_age);
  const { slope_s_per_lap: slope, intercept_s: intercept } = c.fit;
  return [Math.min(...ages), Math.max(...ages)].map((x) => ({ tyre_age: x, fuel_corrected_s: intercept + slope * x }));
}

interface ViewProps {
  data: DegradationResponse;
  focusCode: string | null;
  size?: ChartSize;
}

export function DegradationView({ data, focusCode, size }: ViewProps) {
  const lines = useMemo(() => data.compounds.map(fitLine), [data]);
  if (data.compounds.length === 0) return <ChartMessage text="No laps yet" />;
  return (
    <ChartColumn
      caption={data.compounds.map((c) => (
        <span key={c.compound} data-testid={`deg-legend-${c.compound}`} className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: compoundColor(c.compound) }} />
          {legendText(c)}
        </span>
      ))}
    >
      <ChartArea
        size={size}
        chart={(s) => (
          <ScatterChart margin={{ top: 8, right: 12, bottom: 4, left: 4 }} {...s}>
            <CartesianGrid stroke={GRID_STROKE} />
            <XAxis dataKey="tyre_age" type="number" name="Tyre age" tick={TICK} allowDecimals={false} />
            <YAxis
              dataKey="fuel_corrected_s"
              type="number"
              domain={["auto", "auto"]}
              width={56}
              tick={TICK}
              tickFormatter={(v: number) => formatLapTime(v) ?? ""}
            />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={false} />
            {data.compounds.map((c) => (
              <Scatter
                key={c.compound}
                name={c.compound}
                data={c.points}
                fill={compoundColor(c.compound)}
                isAnimationActive={false}
                shape={(props: { cx?: number; cy?: number; payload?: { code: string } }) => {
                  const focus = props.payload?.code === focusCode;
                  return (
                    <circle
                      cx={props.cx}
                      cy={props.cy}
                      r={focus ? 3.5 : 1.8}
                      fill={compoundColor(c.compound)}
                      fillOpacity={focus ? 1 : 0.55}
                      stroke={focus ? "#fafafa" : "none"}
                      strokeWidth={focus ? 1 : 0}
                      data-focus={focus ? "true" : undefined}
                    />
                  );
                }}
              />
            ))}
            {data.compounds.map((c, i) =>
              lines[i].length ? (
                <Scatter
                  key={`${c.compound}-fit`}
                  name={`${c.compound} fit`}
                  data={lines[i]}
                  line={{ stroke: compoundColor(c.compound), strokeWidth: 2 }}
                  shape={() => <g />}
                  isAnimationActive={false}
                />
              ) : null,
            )}
          </ScatterChart>
        )}
      />
    </ChartColumn>
  );
}

export function Degradation({ ctx, size }: { ctx: ChartContext; size?: ChartSize }) {
  const state = useChartData(ctx, "lap", [], (signal) => fetchDegradation(ctx.raceId, ctx.lap, signal));
  return (
    <ChartBody title={DEGRADATION_TITLE} state={state}>
      {(data) => <DegradationView data={data} focusCode={ctx.focusCode} size={size} />}
    </ChartBody>
  );
}
