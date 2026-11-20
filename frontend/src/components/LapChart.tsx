import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DriverState, LapRow } from "../api/types";
import { chartModel } from "../lib/chartModel";
import { formatLapTime } from "../lib/format";

interface LapChartProps {
  lap: number;
  drivers: DriverState[];
  laps: LapRow[];
  focusCode: string | null;
  /** Fixed size for tests; the dashboard fills its card. */
  size?: { width: number; height: number };
}

export function LapChart({ lap, drivers, laps, focusCode, size }: LapChartProps) {
  const model = useMemo(() => chartModel(drivers, laps, focusCode, lap), [drivers, laps, focusCode, lap]);

  const chart = (
    <LineChart data={model.rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }} {...size}>
      <CartesianGrid stroke="#27272a" vertical={false} />
      <XAxis dataKey="lap" type="number" domain={[1, Math.max(lap, 2)]} tick={{ fill: "#71717a", fontSize: 10 }} />
      <YAxis
        domain={model.domain ?? ["auto", "auto"]}
        allowDataOverflow
        width={56}
        tick={{ fill: "#71717a", fontSize: 10 }}
        tickFormatter={(v: number) => formatLapTime(v) ?? ""}
      />
      <Tooltip
        contentStyle={{ background: "#101013", border: "1px solid #27272a", fontSize: 11 }}
        labelFormatter={(l) => `Lap ${l}`}
        formatter={(v) => formatLapTime(typeof v === "number" ? v : null) ?? "—"}
      />
      {model.series.map((s) => (
        <Line
          key={s.code}
          dataKey={s.code}
          name={s.code}
          type="linear"
          stroke={s.color}
          strokeWidth={s.strokeWidth}
          strokeOpacity={s.opacity}
          dot={s.dots ? { r: 2, fill: s.color, fillOpacity: s.opacity, strokeWidth: 0 } : false}
          activeDot={{ r: 3 }}
          connectNulls={false}
          isAnimationActive={false}
        />
      ))}
    </LineChart>
  );

  return (
    <div className="flex h-full flex-col p-2">
      <div data-testid="chart-legend" className="flex flex-wrap items-center gap-3 px-1 text-xs">
        <span className="text-zinc-500">Neighbours at lap {lap}</span>
        {model.series.map((s) => (
          <span
            key={s.code}
            data-testid={`legend-${s.code}`}
            data-role={s.role}
            className={`flex items-center gap-1 ${s.role === "focus" ? "font-bold text-zinc-100" : "text-zinc-400"}`}
          >
            <span
              className="inline-block rounded"
              style={{ backgroundColor: s.color, opacity: s.opacity, width: 14, height: s.strokeWidth }}
            />
            {s.dots && <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: s.color }} />}
            {s.code}
          </span>
        ))}
      </div>
      <div className="min-h-0 flex-1">
        {size ? chart : <ResponsiveContainer width="100%" height="100%">{chart}</ResponsiveContainer>}
      </div>
    </div>
  );
}
