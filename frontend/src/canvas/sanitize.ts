import { MAX_WIDGETS, type WidgetInstance, type WidgetSettings } from "./board";
import { clampRect, separate } from "./grid";
import { EVENT_TYPES, isWidgetType, MAX_PACE_DRIVERS, REGISTRY, type WidgetType } from "./registry";

// Turns untrusted widget lists (localStorage, imported files) into valid
// widgets: unknown types dropped, geometry clamped to the grid and type
// minimums, overlaps pushed apart, ids made unique, settings limited to the
// type's own settings with known values, at most 24 widgets.

const DRIVER_CODE = /^[A-Z0-9]{1,8}$/;
const WIDGET_ID = /^[A-Za-z0-9_-]{1,40}$/;
export const MAX_NAME_LENGTH = 60;

export interface Sanitized {
  widgets: WidgetInstance[];
  /** Entries dropped: unknown type, not an object, or past the 24-widget cap. */
  skipped: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function num(value: unknown): number {
  return typeof value === "number" ? value : Number.NaN;
}

function settingsFor(type: WidgetType, raw: unknown): WidgetSettings {
  const src = isRecord(raw) ? raw : {};
  const out: WidgetSettings = {};
  const spec = REGISTRY[type].settings;
  if (spec.driver && "driver" in src) {
    out.driver = typeof src.driver === "string" && DRIVER_CODE.test(src.driver) ? src.driver : null;
  }
  if (spec.drivers && Array.isArray(src.drivers)) {
    // Valid codes only, first occurrence kept, at most four, in the file's order.
    const codes: string[] = [];
    for (const c of src.drivers) {
      if (typeof c === "string" && DRIVER_CODE.test(c) && !codes.includes(c)) codes.push(c);
      if (codes.length === MAX_PACE_DRIVERS) break;
    }
    out.drivers = codes;
  }
  if (spec.types && Array.isArray(src.types)) {
    const known = EVENT_TYPES.filter((t) => (src.types as unknown[]).includes(t));
    out.types = [...known];
  }
  return out;
}

export function sanitizeWidgets(raw: unknown): Sanitized {
  const list = Array.isArray(raw) ? raw : [];
  const used = new Set<string>();
  const widgets: WidgetInstance[] = [];
  let skipped = 0;
  for (const entry of list) {
    if (!isRecord(entry) || !isWidgetType(entry.type) || widgets.length >= MAX_WIDGETS) {
      skipped++;
      continue;
    }
    const type = entry.type;
    let id = typeof entry.id === "string" && WIDGET_ID.test(entry.id) && !used.has(entry.id) ? entry.id : "";
    for (let n = 1; !id; n++) if (!used.has(`${type}-${n}`)) id = `${type}-${n}`;
    used.add(id);
    const rect = clampRect({ x: num(entry.x), y: num(entry.y), w: num(entry.w), h: num(entry.h) }, REGISTRY[type].minSize);
    widgets.push({ id, type, ...rect, settings: settingsFor(type, entry.settings) });
  }
  return { widgets: separate(widgets), skipped };
}

/** A board name: a non-empty string, whitespace collapsed, at most 60 characters. */
export function sanitizeName(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const name = raw.replace(/\s+/g, " ").trim().slice(0, MAX_NAME_LENGTH);
  return name || null;
}
