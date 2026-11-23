import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { fetchDegradation } from "../../api/client";
import type { DegradationResponse, DriverState } from "../../api/types";
import { MAX_PACE_DRIVERS } from "../../canvas/registry";
import { formatLapTime } from "../../lib/format";
import { Menu, menuItem } from "../Menu";
import { ChartArea, ChartColumn, type ChartSize, GRID_STROKE, NO_TEAM_COLOR, TICK, TOOLTIP_STYLE } from "./common";
import { ChartBody, type ChartContext, ChartMessage, useChartData } from "./useChartData";

export const PACE_TITLE = "Pace compare";
export const PACE_CAPTION = "Fuel-corrected clean laps";

export interface PaceDrivers {
  codes: string[];
  /** Pinned codes not in this race (skipped). */
  missing: string[];
}

/** The focus driver and the cars directly ahead and behind it at the lap (lap chart rule). */
function focusAndNeighbours(drivers: DriverState[], focusCode: string | null): string[] {
  const focus = drivers.find((d) => d.code === focusCode);
  if (!focus) return [];
  return [focus.position - 1, focus.position, focus.position + 1]
    .map((p) => drivers.find((d) => d.position === p)?.code)
    .filter((c): c is string => c !== undefined);
}

/**
 * Drivers a pace widget plots: the pinned codes that are in the race, or the
 * focus driver and its neighbours when nothing is pinned or no pin remains.
 */
export function paceDrivers(setting: string[] | undefined, drivers: DriverState[], focusCode: string | null): PaceDrivers {
  const pinned = setting ?? [];
  const inRace = new Set(drivers.map((d) => d.code));
  const codes = pinned.filter((c) => inRace.has(c));
  const missing = pinned.filter((c) => !inRace.has(c));
  return { codes: codes.length ? codes : focusAndNeighbours(drivers, focusCode), missing };
}

/** Toggles a code in the setting; a fifth pick is refused (setting unchanged). */
export function togglePaceDriver(setting: string[] | undefined, code: string): string[] {
  const current = setting ?? [];
  if (current.includes(code)) return current.filter((c) => c !== code);
  if (current.length >= MAX_PACE_DRIVERS) return current;
  return [...current, code];
}

export interface PaceSeries {
  code: string;
  color: string;
  dashed: boolean;
}

/** Rows by lap with each selected driver's fuel-corrected time; series in the selection order. */
export function paceModel(data: DegradationResponse, codes: string[], drivers: DriverState[]) {
  const wanted = new Set(codes);
  const byLap = new Map<number, Record<string, number>>();
  const seen = new Set<string>();
  for (const c of data.compounds) {
    for (const p of c.points) {
      if (!wanted.has(p.code)) continue;
      seen.add(p.code);
      const row = byLap.get(p.lap) ?? { lap: p.lap };
      row[p.code] = p.fuel_corrected_s;
      byLap.set(p.lap, row);
    }
  }
  const teams = new Map<string, number>();
  const series: PaceSeries[] = codes.map((code) => {
    const d = drivers.find((x) => x.code === code);
    const team = d?.team ?? code;
    const n = teams.get(team) ?? 0;
    teams.set(team, n + 1);
    // The second driver of a team is dashed so teammates stay apart.
    return { code, color: d?.team_color ?? NO_TEAM_COLOR, dashed: n > 0 };
  });
  return { rows: [...byLap.values()].sort((a, b) => a.lap - b.lap), series, hasPoints: seen.size > 0 };
}

interface ViewProps {
  data: DegradationResponse;
  codes: string[];
  drivers: DriverState[];
  lap: number;
  size?: ChartSize;
}

export function PaceView({ data, codes, drivers, lap, size }: ViewProps) {
  const model = useMemo(() => paceModel(data, codes, drivers), [data, codes, drivers]);
  if (!model.hasPoints) return <ChartMessage text={`No clean laps for ${codes.join(", ") || "these drivers"} yet`} />;
  return (
    <ChartColumn
      caption={
        <>
          {model.series.map((s) => (
            <span key={s.code} data-testid={`pace-legend-${s.code}`} className="flex items-center gap-1">
              <span className="inline-block h-0.5 w-3.5" style={{ backgroundColor: s.color }} />
              {s.code}
            </span>
          ))}
          <span className="text-zinc-500">{PACE_CAPTION}</span>
        </>
      }
    >
      <ChartArea
        size={size}
        chart={(sz) => (
          <LineChart data={model.rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }} {...sz}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis dataKey="lap" type="number" domain={[1, Math.max(lap, 2)]} tick={TICK} />
            <YAxis domain={["auto", "auto"]} width={56} tick={TICK} tickFormatter={(v: number) => formatLapTime(v) ?? ""} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelFormatter={(l) => `Lap ${l}`}
              formatter={(v) => formatLapTime(typeof v === "number" ? v : null) ?? "—"}
            />
            {model.series.map((s) => (
              <Line
                key={s.code}
                dataKey={s.code}
                name={s.code}
                stroke={s.color}
                strokeWidth={2}
                strokeDasharray={s.dashed ? "5 3" : undefined}
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

export function Pace({ ctx, setting, size }: { ctx: ChartContext; setting: string[] | undefined; size?: ChartSize }) {
  const state = useChartData(ctx, "lap", [], (signal) => fetchDegradation(ctx.raceId, ctx.lap, signal));
  const { codes, missing } = paceDrivers(setting, ctx.drivers, ctx.focusCode);
  return (
    <div className="flex h-full flex-col">
      {missing.length > 0 && (
        <p data-testid="pace-missing" className="px-3 pt-2 text-xs text-flag-yellow">
          {missing.join(", ")} not in this race
        </p>
      )}
      <div className="min-h-0 flex-1">
        <ChartBody title={PACE_TITLE} state={state}>
          {(data) => <PaceView data={data} codes={codes} drivers={ctx.drivers} lap={ctx.lap} size={size} />}
        </ChartBody>
      </div>
    </div>
  );
}

/** Title-bar picker: "Follow focus" clears the pins; each driver toggles (at most four). */
export function PaceDriversPicker({
  value,
  drivers,
  onChange,
}: {
  value: string[] | undefined;
  drivers: DriverState[];
  onChange: (drivers: string[]) => void;
}) {
  const pinned = value ?? [];
  const sorted = [...drivers].sort((a, b) => a.position - b.position);
  const full = pinned.length >= MAX_PACE_DRIVERS;
  return (
    <Menu label={pinned.length ? pinned.join(" ") : "Follow focus"} ariaLabel="Drivers for Pace compare widget" align="right">
      {() => (
        <>
          <button type="button" role="menuitemradio" aria-checked={pinned.length === 0} className={menuItem} onClick={() => onChange([])}>
            Follow focus
          </button>
          {sorted.map((d) => {
            const on = pinned.includes(d.code);
            return (
              <button
                key={d.code}
                type="button"
                role="menuitemcheckbox"
                aria-checked={on}
                disabled={!on && full}
                className={menuItem}
                onClick={() => onChange(togglePaceDriver(pinned, d.code))}
              >
                {on ? "✓ " : ""}
                {d.code}
              </button>
            );
          })}
        </>
      )}
    </Menu>
  );
}
