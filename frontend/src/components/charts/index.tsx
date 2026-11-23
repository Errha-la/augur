import { Degradation } from "./Degradation";
import { Heatmap } from "./Heatmap";
import { Pace } from "./Pace";
import { PitClock } from "./PitClock";
import { PitWindow } from "./PitWindow";
import { PositionFan } from "./PositionFan";
import { RaceTrace } from "./RaceTrace";
import { Stints } from "./Stints";
import type { ChartContext } from "./useChartData";

// One component per chart widget type ("One chart component per type with a
// shared data hook"); App.tsx renders them through ChartWidget.

export const CHART_TYPES = ["trace", "pitclock", "pitwindow", "stints", "degradation", "pace", "fan", "heatmap"] as const;
export type ChartType = (typeof CHART_TYPES)[number];

export interface ChartWidgetProps {
  type: ChartType;
  ctx: ChartContext;
  /** The widget's own driver (driver-based charts) or null. */
  code: string | null;
  /** Pace widget: its `drivers` setting (pinned codes; empty follows the focus driver). */
  codes?: string[];
}

export function ChartWidget({ type, ctx, code, codes }: ChartWidgetProps) {
  switch (type) {
    case "trace":
      return <RaceTrace ctx={ctx} />;
    case "stints":
      return <Stints ctx={ctx} />;
    case "degradation":
      return <Degradation ctx={ctx} />;
    case "heatmap":
      return <Heatmap ctx={ctx} />;
    case "pitclock":
      return <PitClock ctx={ctx} code={code} />;
    case "pitwindow":
      return <PitWindow ctx={ctx} code={code} />;
    case "fan":
      return <PositionFan ctx={ctx} code={code} />;
    case "pace":
      return <Pace ctx={ctx} setting={codes} />;
  }
}
