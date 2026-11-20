import { useMemo } from "react";
import { Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import type { LapData, PositionsHistoryResponse, StrategyResponse } from "../api/types";
import { useKeyedFetch } from "../hooks/useKeyedFetch";
import { formatDeg, formatExpectedPosition, formatLapTime, formatPct } from "../lib/format";
import { stintsOf } from "../lib/laps";
import { compoundColor, compoundLetter, eventTypeLabel } from "../lib/theme";
import { OrDash } from "./Dash";
import { StrategyTable } from "./StrategyTable";

export const GREEN_RACE_NOTE = "Assumes a green race to the end";

const WIN_COLOR = "#c084fc";
const PODIUM_COLOR = "#34d399";

interface FocusPanelProps {
  data: LapData;
  focusCode: string;
  playing: boolean;
  /** Fixed chart size for tests; the dashboard fills the card. */
  chartSize?: { width: number; height: number };
}

/**
 * Strategy and probability history are slow (simulations), so they refresh
 * only while paused, or during playback on laps divisible by 5.
 */
export function refreshesAt(lap: number, playing: boolean): boolean {
  return !playing || lap % 5 === 0;
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] tracking-wider text-zinc-500">{label}</div>
      <div className="font-bold tabular-nums">{children}</div>
    </div>
  );
}

export function FocusPanel({ data, focusCode, playing, chartSize }: FocusPanelProps) {
  const { raceId, lap } = data;
  const driver = data.state.drivers.find((d) => d.code === focusCode);
  const pred = data.predictions.drivers.find((p) => p.code === focusCode);
  const pos = data.positions.drivers.find((p) => p.code === focusCode);
  const stints = useMemo(() => stintsOf(data.laps, focusCode, lap), [data.laps, focusCode, lap]);
  const events = data.events.events.filter((e) => e.drivers.includes(focusCode));

  const refresh = refreshesAt(lap, playing);
  const strategy = useKeyedFetch<StrategyResponse>(refresh ? `${raceId}|${lap}|${focusCode}` : null, (signal) =>
    api.strategy(raceId, lap, focusCode, signal),
  );
  const history = useKeyedFetch<PositionsHistoryResponse>(refresh ? `${raceId}|${lap}` : null, (signal) =>
    api.positionsHistory(raceId, lap, signal),
  );

  // Requests keep running across laps and focus changes; show only what belongs
  // to the race and driver on screen (keys are `${raceId}|${lap}|${code}`).
  const forFocus = (key: string | null) => key !== null && key.startsWith(`${raceId}|`) && key.endsWith(`|${focusCode}`);
  const strategyShown =
    strategy.value && strategy.value.race_id === raceId && strategy.value.driver === focusCode ? strategy.value : null;
  const strategyLoading = forFocus(strategy.loadingKey);
  const strategyError = forFocus(strategy.errorKey) ? strategy.error : null;
  const historyRows = useMemo(() => {
    if (!history.value || history.value.race_id !== raceId) return [];
    return history.value.laps
      .filter((l) => l.lap <= lap)
      .map((l) => {
        const d = l.drivers.find((x) => x.code === focusCode);
        return {
          lap: l.lap,
          win: d?.p_win == null ? null : d.p_win * 100,
          podium: d?.p_podium == null ? null : d.p_podium * 100,
        };
      });
  }, [history.value, raceId, lap, focusCode]);
  const nextRefresh = Math.ceil((lap + 1) / 5) * 5;

  if (!driver) return null;
  const totalStintLaps = stints.reduce((n, s) => n + s.laps, 0);

  const historyChart = (
    <LineChart data={historyRows} margin={{ top: 4, right: 8, bottom: 0, left: -16 }} {...chartSize}>
      <XAxis dataKey="lap" type="number" domain={[1, Math.max(lap, 2)]} tick={{ fill: "#71717a", fontSize: 9 }} />
      <YAxis domain={[0, 100]} ticks={[0, 50, 100]} tick={{ fill: "#71717a", fontSize: 9 }} />
      <Tooltip
        contentStyle={{ background: "#101013", border: "1px solid #27272a", fontSize: 11 }}
        labelFormatter={(l) => `Lap ${l}`}
        formatter={(v) => (typeof v === "number" ? `${Math.round(v)}%` : "—")}
      />
      <Legend iconSize={8} wrapperStyle={{ fontSize: 10 }} />
      <Line dataKey="win" name="WIN" stroke={WIN_COLOR} dot={false} strokeWidth={1.5} isAnimationActive={false} />
      <Line dataKey="podium" name="PODIUM" stroke={PODIUM_COLOR} dot={false} strokeWidth={1.5} isAnimationActive={false} />
    </LineChart>
  );

  return (
    <div data-testid="focus-panel" className="flex flex-col gap-3 p-3 text-sm">
      <div className="flex items-center gap-2">
        <span className="h-6 w-1.5 rounded" style={{ backgroundColor: driver.team_color }} />
        <span className="text-2xl font-bold">{driver.code}</span>
        <span className="text-zinc-400">{driver.team}</span>
      </div>

      <div>
        <div className="mb-1 text-[10px] tracking-wider text-zinc-500">STINTS TO LAP {lap}</div>
        <div data-testid="stint-bar" className="flex h-3 w-full gap-px overflow-hidden rounded bg-zinc-900">
          {stints.map((s) => (
            <div
              key={s.stint}
              data-testid="stint-segment"
              data-compound={s.compound ?? ""}
              data-laps={s.laps}
              title={`${s.compound ?? "Unknown"} · ${s.laps} laps`}
              style={{ flexGrow: s.laps, flexBasis: 0, backgroundColor: compoundColor(s.compound) }}
            />
          ))}
        </div>
        <div className="mt-0.5 flex text-[10px] text-zinc-500">
          {stints.map((s) => (
            <span key={s.stint} style={{ flexGrow: s.laps, flexBasis: 0 }} className="truncate">
              {compoundLetter(s.compound) ?? "?"} {s.laps}
            </span>
          ))}
          {totalStintLaps === 0 && <span>No laps yet</span>}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Stat label="DEGRADATION">
          <span data-testid="focus-deg">
            <OrDash text={formatDeg(pred?.deg_s_per_lap)} />
          </span>
          {pred?.cliff && (
            <span className="ml-1 rounded bg-flag-red/20 px-1 text-[10px] font-bold text-flag-red">CLIFF</span>
          )}
        </Stat>
        <Stat label="NEXT LAP">
          <OrDash text={formatLapTime(pred?.predicted_next_lap_s)} />
        </Stat>
        <Stat label="EXPECTED">
          <span data-testid="focus-expected">
            {pos && formatExpectedPosition(pos.expected_position) ? (
              `${formatExpectedPosition(pos.expected_position)} (${formatExpectedPosition(pos.position_p10) ?? "?"}-${
                formatExpectedPosition(pos.position_p90) ?? "?"
              })`
            ) : (
              <OrDash text={null} />
            )}
          </span>
        </Stat>
      </div>

      <div>
        <div data-testid="focus-probabilities" className="flex gap-4 font-bold tabular-nums">
          <span>
            WIN <OrDash text={formatPct(pos?.p_win)} />
          </span>
          <span>
            PODIUM <OrDash text={formatPct(pos?.p_podium)} />
          </span>
          <span>
            POINTS <OrDash text={formatPct(pos?.p_points)} />
          </span>
        </div>
        <p className="mt-0.5 text-[11px] text-zinc-500">{GREEN_RACE_NOTE}</p>
        <div data-testid="probability-history" className="mt-1 h-28">
          {history.loading && historyRows.length === 0 ? (
            <p className="text-xs text-zinc-500">Simulating...</p>
          ) : chartSize ? (
            historyChart
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              {historyChart}
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <StrategyTable
        response={strategyShown}
        loading={strategyLoading}
        error={strategyError}
        idleText={`Strategy updates at lap ${nextRefresh} or when paused`}
      />

      <div>
        <div className="mb-1 text-[10px] tracking-wider text-zinc-500">EVENTS · {driver.code}</div>
        {events.length === 0 ? (
          <p className="text-xs text-zinc-500">No events for {driver.code} yet</p>
        ) : (
          <ul data-testid="focus-events" className="flex flex-col gap-1 text-xs">
            {events.map((e) => (
              <li key={e.id} className="flex gap-2">
                <span className="text-zinc-500 tabular-nums">L{e.lap}</span>
                <span className="text-zinc-400">{eventTypeLabel(e.type)}</span>
                <span className="truncate">{e.title}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
