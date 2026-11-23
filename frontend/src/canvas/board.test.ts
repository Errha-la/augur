import { describe, expect, it } from "vitest";
import { addWidget, BOARD_FULL, type Board, MAX_WIDGETS, moveWidget, removeWidget, updateSettings } from "./board";
import { REGISTRY, WIDGET_TYPES } from "./registry";

const empty: Board = { id: "b", name: "Board 1", presetId: null, widgets: [] };

function add(board: Board, type: Parameters<typeof addWidget>[1]): Board {
  const r = addWidget(board, type);
  if (!r.ok) throw new Error(r.message);
  return r.board;
}

describe("board model", () => {
  it("registers the five widget types with defaults no smaller than their minimums", () => {
    expect(WIDGET_TYPES).toEqual(["timing", "events", "driver", "lapchart", "timeline"]);
    for (const t of WIDGET_TYPES) {
      const { defaultSize, minSize } = REGISTRY[t];
      expect(defaultSize.w).toBeGreaterThanOrEqual(minSize.w);
      expect(defaultSize.h).toBeGreaterThanOrEqual(minSize.h);
    }
  });

  it("Same type twice: two driver widgets get distinct ids and separate settings", () => {
    const board = add(add(empty, "driver"), "driver");
    const [a, b] = board.widgets;
    expect(a.type).toBe("driver");
    expect(b.type).toBe("driver");
    expect(a.id).not.toBe(b.id);
    const pinned = updateSettings(board, b.id, { driver: "PIA" });
    expect(pinned.widgets[0].settings.driver).toBeUndefined();
    expect(pinned.widgets[1].settings.driver).toBe("PIA");
    const moved = moveWidget(pinned, b.id, 6, 0);
    expect(moved.widgets[1]).toMatchObject({ x: 6, y: 0 });
    expect(moved.widgets[0]).toMatchObject({ x: 0, y: 0 });
  });

  it("adds a widget below the lowest widget at its default size", () => {
    const board = add(add(empty, "timing"), "lapchart");
    expect(board.widgets[1]).toMatchObject({ x: 0, y: 10, w: 7, h: 5 });
  });

  it("Board full: a 24-widget board refuses another widget and is unchanged", () => {
    let board = empty;
    for (let i = 0; i < MAX_WIDGETS; i++) board = add(board, "timeline");
    const r = addWidget(board, "driver");
    expect(r).toEqual({ ok: false, message: BOARD_FULL });
    expect(board.widgets).toHaveLength(24);
  });

  it("removing a widget compacts the rest upward", () => {
    const board = add(add(empty, "timeline"), "timing");
    const out = removeWidget(board, board.widgets[0].id);
    expect(out.widgets).toEqual([expect.objectContaining({ type: "timing", y: 0 })]);
  });
});
