import type { ReactElement, ReactNode } from "react";
import { ResponsiveContainer } from "recharts";

/** Fixed chart size for tests; the dashboard fills the widget body. */
export type ChartSize = { width: number; height: number } | undefined;

export const TICK = { fill: "#71717a", fontSize: 10 } as const;
export const GRID_STROKE = "#27272a";
export const TOOLTIP_STYLE = { background: "#101013", border: "1px solid #27272a", fontSize: 11 } as const;
/** Colour for a driver without a team colour. */
export const NO_TEAM_COLOR = "#a1a1aa";

/** Renders `chart` (a Recharts root that takes width/height props) at `size`, or filling its parent. */
export function ChartArea({ size, chart }: { size: ChartSize; chart: (size: ChartSize) => ReactElement }) {
  return (
    <div className="min-h-0 flex-1">
      {size ? chart(size) : <ResponsiveContainer width="100%" height="100%">{chart(undefined)}</ResponsiveContainer>}
    </div>
  );
}

/** Widget body column: optional caption row on top, chart below. */
export function ChartColumn({ caption, children }: { caption?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex h-full flex-col p-2">
      {caption && (
        <div data-testid="chart-caption" className="flex flex-wrap items-center gap-3 px-1 text-xs text-zinc-400">
          {caption}
        </div>
      )}
      {children}
    </div>
  );
}

export function colorOf(colors: Record<string, string | null | undefined>, code: string): string {
  return colors[code] ?? NO_TEAM_COLOR;
}
