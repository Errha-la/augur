import type { Size } from "./grid";

// Widget types of a board ("Widget instances with settings"). The components
// that render each type live in components/widgets.tsx under the same keys.

export const WIDGET_TYPES = [
  "timing",
  "events",
  "driver",
  "lapchart",
  "timeline",
  "trace",
  "pitclock",
  "pitwindow",
  "stints",
  "degradation",
  "pace",
  "fan",
  "heatmap",
] as const;
export type WidgetType = (typeof WIDGET_TYPES)[number];

/** Event types an `events` widget can filter on (the /events types). */
export const EVENT_TYPES = [
  "degradation_warning",
  "undercut_window",
  "overcut_window",
  "position_change",
  "pace_drop",
] as const;

export interface WidgetSpec {
  title: string;
  defaultSize: Size;
  minSize: Size;
  /** Settings this type has: a driver picker, a driver list (pace), and/or event-type chips. */
  settings: { driver: boolean; drivers: boolean; types: boolean };
}

const NONE = { driver: false, drivers: false, types: false };
const DRIVER = { ...NONE, driver: true };

/** Sizes are grid cells (w x h); see the design's Implementation Contract table. */
export const REGISTRY: Record<WidgetType, WidgetSpec> = {
  timing: { title: "Timing", defaultSize: { w: 5, h: 10 }, minSize: { w: 4, h: 4 }, settings: NONE },
  events: { title: "Events", defaultSize: { w: 7, h: 6 }, minSize: { w: 3, h: 4 }, settings: { ...NONE, types: true } },
  driver: { title: "Driver", defaultSize: { w: 5, h: 8 }, minSize: { w: 3, h: 5 }, settings: DRIVER },
  lapchart: { title: "Lap times", defaultSize: { w: 7, h: 5 }, minSize: { w: 3, h: 4 }, settings: DRIVER },
  timeline: { title: "Timeline", defaultSize: { w: 12, h: 2 }, minSize: { w: 4, h: 2 }, settings: NONE },
  trace: { title: "Race trace", defaultSize: { w: 12, h: 6 }, minSize: { w: 4, h: 4 }, settings: NONE },
  pitclock: { title: "Pit clock", defaultSize: { w: 5, h: 6 }, minSize: { w: 4, h: 5 }, settings: DRIVER },
  pitwindow: { title: "Pit window", defaultSize: { w: 7, h: 6 }, minSize: { w: 4, h: 4 }, settings: DRIVER },
  stints: { title: "Tyre stints", defaultSize: { w: 7, h: 7 }, minSize: { w: 4, h: 4 }, settings: NONE },
  degradation: { title: "Degradation", defaultSize: { w: 5, h: 7 }, minSize: { w: 4, h: 4 }, settings: NONE },
  pace: { title: "Pace compare", defaultSize: { w: 7, h: 6 }, minSize: { w: 4, h: 4 }, settings: { ...NONE, drivers: true } },
  fan: { title: "Position fan", defaultSize: { w: 6, h: 5 }, minSize: { w: 4, h: 4 }, settings: DRIVER },
  heatmap: { title: "Position odds", defaultSize: { w: 7, h: 8 }, minSize: { w: 4, h: 5 }, settings: NONE },
};

/** Most drivers a pace widget compares. */
export const MAX_PACE_DRIVERS = 4;

export function isWidgetType(value: unknown): value is WidgetType {
  return typeof value === "string" && (WIDGET_TYPES as readonly string[]).includes(value);
}
