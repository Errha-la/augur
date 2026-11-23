import { bottom, compact, moveItem, resizeItem } from "./grid";
import { REGISTRY, type WidgetType } from "./registry";

export type { WidgetType } from "./registry";

export const MAX_WIDGETS = 24;
export const BOARD_FULL = "A board holds at most 24 widgets";

export interface WidgetSettings {
  /** Driver widgets: null or absent follows the focus driver; a code pins it. */
  driver?: string | null;
  /** Pace widget: one to four pinned codes; absent or empty follows the focus driver and its neighbours. */
  drivers?: string[];
  /** Events widget: the event types shown; absent shows every type. */
  types?: string[];
}

export interface WidgetInstance {
  id: string;
  type: WidgetType;
  x: number;
  y: number;
  w: number;
  h: number;
  settings: WidgetSettings;
}

export type PresetId = "pit" | "battle" | "pace" | "strategy";

export interface Board {
  id: string;
  name: string;
  presetId: PresetId | null;
  widgets: WidgetInstance[];
}

/** A widget id not used on `board`: `<type>-<n>` with the lowest free n. */
export function nextWidgetId(widgets: readonly WidgetInstance[], type: WidgetType): string {
  const used = new Set(widgets.map((w) => w.id));
  let n = 1;
  while (used.has(`${type}-${n}`)) n++;
  return `${type}-${n}`;
}

export type AddResult = { ok: true; board: Board; id: string } | { ok: false; message: typeof BOARD_FULL };

/** Adds `type` below the lowest widget at its default size. */
export function addWidget(board: Board, type: WidgetType): AddResult {
  if (board.widgets.length >= MAX_WIDGETS) return { ok: false, message: BOARD_FULL };
  const { w, h } = REGISTRY[type].defaultSize;
  const id = nextWidgetId(board.widgets, type);
  const widget: WidgetInstance = { id, type, x: 0, y: bottom(board.widgets), w, h, settings: {} };
  return { ok: true, id, board: { ...board, widgets: [...board.widgets, widget] } };
}

export function removeWidget(board: Board, id: string): Board {
  return { ...board, widgets: compact(board.widgets.filter((w) => w.id !== id)) };
}

export function minSizeOf(widget: WidgetInstance) {
  return REGISTRY[widget.type].minSize;
}

export function moveWidget(board: Board, id: string, x: number, y: number): Board {
  const widget = board.widgets.find((w) => w.id === id);
  if (!widget) return board;
  return { ...board, widgets: moveItem(board.widgets, id, x, y, minSizeOf(widget)) };
}

export function resizeWidget(board: Board, id: string, w: number, h: number): Board {
  const widget = board.widgets.find((x) => x.id === id);
  if (!widget) return board;
  return { ...board, widgets: resizeItem(board.widgets, id, w, h, minSizeOf(widget)) };
}

export function updateSettings(board: Board, id: string, patch: Partial<WidgetSettings>): Board {
  return {
    ...board,
    widgets: board.widgets.map((w) => (w.id === id ? { ...w, settings: { ...w.settings, ...patch } } : w)),
  };
}

/** True when two boards hold the same name and widgets (ignoring id). */
export function sameBoard(a: Board, b: Board): boolean {
  return a.name === b.name && JSON.stringify(a.widgets) === JSON.stringify(b.widgets);
}
