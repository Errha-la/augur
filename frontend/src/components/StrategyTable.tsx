import type { StrategyResponse } from "../api/types";
import { formatPct, formatRaceTime } from "../lib/format";
import { OrDash } from "./Dash";

interface StrategyTableProps {
  response: StrategyResponse | null;
  loading: boolean;
  error: Error | null;
  /** Shown when there is neither a response nor a request in flight. */
  idleText?: string;
}

/** Strategy, mean race time, p10-p90 range and win probability. */
export function StrategyTable({ response, loading, error, idleText }: StrategyTableProps) {
  if (loading) {
    return (
      <p data-testid="simulating" className="py-1 text-xs text-zinc-500">
        Simulating...
      </p>
    );
  }
  if (error) return <p className="py-1 text-xs text-flag-red">Strategy unavailable: {error.message}</p>;
  if (!response) return idleText ? <p className="py-1 text-xs text-zinc-500">{idleText}</p> : null;

  return (
    <table data-testid="strategy-table" className="w-full text-xs tabular-nums">
      <caption className="pb-1 text-left text-[10px] tracking-wider text-zinc-500">
        STRATEGY · {response.driver} AT LAP {response.lap} · {response.runs} RUNS
      </caption>
      <thead className="text-left text-[10px] text-zinc-500">
        <tr>
          <th className="pr-2 font-normal">STRATEGY</th>
          <th className="pr-2 text-right font-normal">MEAN</th>
          <th className="pr-2 text-right font-normal">P10-P90</th>
          <th className="text-right font-normal">WIN</th>
        </tr>
      </thead>
      <tbody>
        {response.strategies.map((s) => (
          <tr key={s.name} className="border-t border-zinc-800/60">
            <td className="pr-2">{s.name}</td>
            <td className="pr-2 text-right">
              <OrDash text={formatRaceTime(s.mean_s)} />
            </td>
            <td className="pr-2 text-right whitespace-nowrap text-zinc-400">
              {s.p10_s == null || s.p90_s == null ? (
                <OrDash text={null} />
              ) : (
                `${formatRaceTime(s.p10_s)}–${formatRaceTime(s.p90_s)}`
              )}
            </td>
            <td className="text-right">
              <OrDash text={formatPct(s.win_probability)} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
