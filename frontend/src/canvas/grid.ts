// Snap-grid engine for boards ("Own grid engine instead of a library"): pure
// functions over integer cell rectangles. Widgets never overlap; after every
// change they compact upward, and the widget being moved or resized stays where
// the viewer put it while the others make room below it.

export const COLS = 12;
export const ROW_HEIGHT = 44;
export const GAP = 8;

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Size {
  w: number;
  h: number;
}

export type GridItem = Rect & { id: string };

export function collides(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

function int(value: number, fallback: number): number {
  return Number.isFinite(value) ? Math.round(value) : fallback;
}

/** Clamps a rectangle to the 12 columns and to at least `min` cells. */
export function clampRect<T extends Rect>(item: T, min: Size): T {
  const w = Math.min(COLS, Math.max(min.w, int(item.w, min.w)));
  const h = Math.max(min.h, int(item.h, min.h));
  const x = Math.min(COLS - w, Math.max(0, int(item.x, 0)));
  const y = Math.max(0, int(item.y, 0));
  return { ...item, x, y, w, h };
}

/**
 * Compacts items upward without overlaps. `fixedId` (the widget being moved or
 * resized) keeps its position; items in its way are pushed below it. Items are
 * placed in row-then-column order, so their relative order is kept.
 */
export function compact<T extends GridItem>(items: readonly T[], fixedId?: string): T[] {
  const fixed = fixedId === undefined ? undefined : items.find((i) => i.id === fixedId);
  const placed: T[] = fixed ? [fixed] : [];
  const rest = items.filter((i) => i !== fixed).sort((a, b) => a.y - b.y || a.x - b.x);
  for (const item of rest) {
    let y = item.y;
    while (y > 0 && !placed.some((p) => collides({ ...item, y: y - 1 }, p))) y--;
    while (placed.some((p) => collides({ ...item, y }, p))) y++;
    placed.push(y === item.y ? item : { ...item, y });
  }
  // Keep the caller's order so React keys and reading order stay stable.
  const byId = new Map(placed.map((p) => [p.id, p]));
  return items.map((i) => byId.get(i.id) ?? i);
}

/**
 * Removes overlaps by pushing items down, never up, so a stored or imported
 * board keeps every position that was valid (including gaps the viewer left).
 */
export function separate<T extends GridItem>(items: readonly T[]): T[] {
  const placed: T[] = [];
  for (const item of [...items].sort((a, b) => a.y - b.y || a.x - b.x)) {
    let y = item.y;
    while (placed.some((p) => collides({ ...item, y }, p))) y++;
    placed.push(y === item.y ? item : { ...item, y });
  }
  const byId = new Map(placed.map((p) => [p.id, p]));
  return items.map((i) => byId.get(i.id) ?? i);
}

/** Moves item `id` to (x, y), clamped, and lays out the others around it. */
export function moveItem<T extends GridItem>(items: readonly T[], id: string, x: number, y: number, min: Size): T[] {
  return compact(
    items.map((i) => (i.id === id ? clampRect({ ...i, x, y }, min) : i)),
    id,
  );
}

/** Resizes item `id` to w × h, never below `min` or past the right edge. */
export function resizeItem<T extends GridItem>(items: readonly T[], id: string, w: number, h: number, min: Size): T[] {
  return compact(
    items.map((i) => {
      if (i.id !== id) return i;
      const width = Math.min(COLS - i.x, Math.max(min.w, int(w, i.w)));
      return { ...i, w: width, h: Math.max(min.h, int(h, i.h)) };
    }),
    id,
  );
}

/** The first row below every item: where a new widget goes. */
export function bottom(items: readonly Rect[]): number {
  return items.reduce((n, i) => Math.max(n, i.y + i.h), 0);
}

/** Reading order for the single-column view: row, then column. */
export function readingOrder<T extends Rect>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => a.y - b.y || a.x - b.x);
}

/** Width of one column in px for a board `width` px wide. */
export function columnWidth(width: number): number {
  return Math.max(0, (width - GAP * (COLS - 1)) / COLS);
}

/** Pixel box of a cell rectangle. */
export function toPixels(rect: Rect, colWidth: number): { left: number; top: number; width: number; height: number } {
  return {
    left: rect.x * (colWidth + GAP),
    top: rect.y * (ROW_HEIGHT + GAP),
    width: rect.w * colWidth + (rect.w - 1) * GAP,
    height: heightPx(rect.h),
  };
}

export function heightPx(h: number): number {
  return h * ROW_HEIGHT + (h - 1) * GAP;
}

/** Cells covered by a pointer move of dx × dy px (rounded to the nearest cell). */
export function cellDelta(dx: number, dy: number, colWidth: number): { dx: number; dy: number } {
  const col = colWidth + GAP;
  return {
    dx: col > 0 ? Math.round(dx / col) : 0,
    dy: Math.round(dy / (ROW_HEIGHT + GAP)),
  };
}
