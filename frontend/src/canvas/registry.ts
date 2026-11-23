import type { Size } from "./grid";

// Widget types of a board ("Widget instances with settings"). The components
// that render each type live in components/widgets.tsx under the same keys.

export const WIDGET_TYPES = ["timing", "events", "driver", "lapchart", "timeline"] as const;
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
  /** Settings this type has: a driver picker and/or event-type chips. */
  settings: { driver: boolean; types: boolean };
}

export const REGISTRY: Record<WidgetType, WidgetSpec> = {
  timing: { title: "Timing", defaultSize: { w: 5, h: 10 }, minSize: { w: 4, h: 4 }, settings: { driver: false, types: false } },
  events: { title: "Events", defaultSize: { w: 7, h: 6 }, minSize: { w: 3, h: 4 }, settings: { driver: false, types: true } },
  driver: { title: "Driver", defaultSize: { w: 5, h: 8 }, minSize: { w: 3, h: 5 }, settings: { driver: true, types: false } },
  lapchart: { title: "Lap times", defaultSize: { w: 7, h: 5 }, minSize: { w: 3, h: 4 }, settings: { driver: true, types: false } },
  timeline: { title: "Timeline", defaultSize: { w: 12, h: 2 }, minSize: { w: 4, h: 2 }, settings: { driver: false, types: false } },
};

export function isWidgetType(value: unknown): value is WidgetType {
  return typeof value === "string" && (WIDGET_TYPES as readonly string[]).includes(value);
}
