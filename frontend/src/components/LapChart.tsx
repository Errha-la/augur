import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DriverState, LapRow } from "../api/types";
import type { PredictionHistory } from "../hooks/usePredictionHistory";
import { chartModel, type NeutralisedLap, type PitMarker } from "../lib/chartModel";
import { formatLapTime } from "../lib/format";

/** Horizontal step between two "P" labels on the same lap. */
const SAME_LAP_OFFSET_PX = 10;

interface Box {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
}

/** Shaded column for one SC / VSC / red-flag lap; the first lap of a run carries the label at the bottom. */
function NeutralisedBand({ lap, label, showLabel, box }: NeutralisedLap & { box: Box }) {
  const { x = 0, y = 0, width = 0, height = 0 } = box;
  return (
    <g data-testid="neutralised-lap" data-lap={lap} data-label={label}>
      <rect x={x} y={y} width={width} height={height} fill="#facc15" fillOpacity={0.12} />
      {showLabel && (
        <text x={x + 2} y={y + height - 4} fill="#a1a1aa" fontSize={8}>
          {label}
        </text>
      )}
    </g>
  );
}

/** "P" in the driver's colour just inside the top of the plot on the pit-in lap. */
function PitLabel({ marker, cx, cy, offset }: { marker: PitMarker; cx?: number; cy?: number; offset: number }) {
  return (
    <text
      data-testid="pit-marker"
      data-code={marker.code}
      data-lap={marker.lap}
      x={(cx ?? 0) + offset}
      y={(cy ?? 0) + 11}
      textAnchor="middle"
      fill={marker.color}
      fontSize={10}
      fontWeight={700}
    >
      P
    </text>
  );
}

/** Index of each marker among the markers on its lap, for the side-by-side offset. */
function sameLapIndex(markers: PitMarker[]): number[] {
  const seen = new Map<number, number>();
  return markers.map((m) => {
    const i = seen.get(m.lap) ?? 0;
    seen.set(m.lap, i + 1);
    return i;
  });
}

interface LapChartProps {
  lap: number;
  drivers: DriverState[];
  laps: LapRow[];
  /** Predictions made at laps 1..lap-1 (see usePredictionHistory). */
  predicted?: PredictionHistory;
  focusCode: string | null;
  /** Fixed size for tests; the dashboard fills its card. */
  size?: { width: number; height: number };
}

export function LapChart({ lap, drivers, laps, predicted, focusCode, size }: LapChartProps) {
  const model = useMemo(
    () => chartModel(drivers, laps, focusCode, lap, predicted),
    [drivers, laps, focusCode, lap, predicted],
  );

  const offsets = sameLapIndex(model.pitMarkers);
  const top = model.domain?.[1];

  const chart = (
    <LineChart data={model.rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }} {...size}>
      <CartesianGrid stroke="#27272a" vertical={false} />
      {model.neutralised.map((n) => (
        <ReferenceArea
          key={`band-${n.lap}`}
          x1={n.lap - 0.5}
          x2={n.lap + 0.5}
          ifOverflow="hidden"
          shape={(box: Box) => <NeutralisedBand {...n} box={box} />}
        />
      ))}
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
      {model.hasPredictions &&
        model.series.map((s) => (
          <Line
            key={s.predKey}
            dataKey={s.predKey}
            name={`${s.code} predicted`}
            type="linear"
            stroke={s.color}
            strokeWidth={1.5}
            strokeOpacity={s.opacity}
            strokeDasharray="4 3"
            dot={false}
            activeDot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
        ))}
      {top !== undefined &&
        model.pitMarkers.map((m, i) => (
          <ReferenceDot
            key={`pit-${m.code}-${m.lap}`}
            x={m.lap}
            y={top}
            ifOverflow="visible"
            shape={(p: { cx?: number; cy?: number }) => (
              <PitLabel marker={m} cx={p.cx} cy={p.cy} offset={offsets[i] * SAME_LAP_OFFSET_PX} />
            )}
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
        {model.hasPredictions && <span className="text-zinc-500">dashed: predicted</span>}
        {model.pitMarkers.length > 0 && (
          <span data-testid="legend-pit" className="text-zinc-500">
            <span className="font-bold text-zinc-300">P</span> pit stop
          </span>
        )}
        {model.neutralised.length > 0 && (
          <span data-testid="legend-neutralised" className="flex items-center gap-1 text-zinc-500">
            <span className="inline-block h-2.5 w-2.5" style={{ backgroundColor: "rgba(250, 204, 21, 0.25)" }} />
            SC / VSC
          </span>
        )}
      </div>
      <div className="min-h-0 flex-1">
        {size ? chart : <ResponsiveContainer width="100%" height="100%">{chart}</ResponsiveContainer>}
      </div>
    </div>
  );
}
