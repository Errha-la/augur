import { fetchPositionDistribution } from "../../api/client";
import type { PositionDistributionResponse } from "../../api/types";
import { colorOf } from "./common";
import { ChartBody, type ChartContext, ChartMessage, useChartData } from "./useChartData";

export const HEATMAP_TITLE = "Position odds";
export const NOT_ANALYZED = "Race not analyzed";
export const NO_DISTRIBUTION = "No distribution stored; re-run analyze";
/** Cells at or above this share show their percentage. */
export const LABEL_MIN_SHARE = 0.1;

export function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

/** Written in the cell only from 10 % (with a small tolerance for float shares like 0.1). */
export function cellLabel(share: number): string | null {
  return share >= LABEL_MIN_SHARE - 1e-9 ? percent(share) : null;
}

interface ViewProps {
  data: PositionDistributionResponse;
  teamColors: Record<string, string | null | undefined>;
}

export function HeatmapView({ data, teamColors }: ViewProps) {
  if (!data.analyzed) return <ChartMessage text={NOT_ANALYZED} />;
  if (data.drivers.every((d) => d.position_distribution === null)) return <ChartMessage text={NO_DISTRIBUTION} />;
  const columns = Math.max(data.drivers.length, ...data.drivers.map((d) => d.position_distribution?.length ?? 0));
  const grid = { gridTemplateColumns: `2.5rem repeat(${columns}, minmax(1.25rem, 1fr))` };
  return (
    <div className="p-2 text-[10px]">
      <div className="grid gap-px" style={grid}>
        <span />
        {Array.from({ length: columns }, (_, i) => (
          <span key={i} className="text-center text-zinc-500">
            P{i + 1}
          </span>
        ))}
      </div>
      {data.drivers.map((d) => (
        <div key={d.code} data-testid={`odds-${d.code}`} className="grid gap-px" style={grid}>
          <span className="text-zinc-300">{d.code}</span>
          {Array.from({ length: columns }, (_, i) => {
            const share = d.position_distribution?.[i] ?? null;
            return (
              <span
                key={i}
                data-testid="odds-cell"
                title={share === null ? `${d.code} P${i + 1}` : `${d.code} P${i + 1}: ${percent(share)}`}
                className="relative flex h-4 items-center justify-center rounded-sm bg-zinc-900"
              >
                {share !== null && share > 0 && (
                  <span
                    className="absolute inset-0 rounded-sm"
                    style={{ backgroundColor: colorOf(teamColors, d.code), opacity: share }}
                  />
                )}
                <span className="relative font-bold text-zinc-50">{share === null ? null : cellLabel(share)}</span>
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

export function Heatmap({ ctx }: { ctx: ChartContext }) {
  const state = useChartData(ctx, "lap", [], (signal) => fetchPositionDistribution(ctx.raceId, ctx.lap, signal));
  const teamColors = Object.fromEntries(ctx.drivers.map((d) => [d.code, d.team_color]));
  return (
    <ChartBody title={HEATMAP_TITLE} state={state}>
      {(data) => <HeatmapView data={data} teamColors={teamColors} />}
    </ChartBody>
  );
}
