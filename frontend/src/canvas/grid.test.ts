import { describe, expect, it } from "vitest";
import { cellDelta, clampRect, collides, columnWidth, compact, type GridItem, moveItem, resizeItem, toPixels } from "./grid";

const MIN = { w: 2, h: 2 };

function noOverlaps(items: GridItem[]) {
  for (const a of items) for (const b of items) if (a !== b) expect(collides(a, b)).toBe(false);
}

describe("grid engine", () => {
  it("Push down on drop: B dragged onto A pushes A below it", () => {
    const items = [
      { id: "A", x: 0, y: 0, w: 6, h: 4 },
      { id: "B", x: 0, y: 4, w: 6, h: 4 },
    ];
    const out = moveItem(items, "B", 0, 2, MIN);
    expect(out.find((i) => i.id === "B")).toMatchObject({ x: 0, y: 2 });
    expect(out.find((i) => i.id === "A")).toMatchObject({ x: 0, y: 6 });
    noOverlaps(out);
  });

  it("Compaction after removal: the remaining widget moves up to (0,0)", () => {
    const items = [
      { id: "A", x: 0, y: 0, w: 12, h: 3 },
      { id: "B", x: 0, y: 3, w: 6, h: 4 },
    ];
    const out = compact(items.filter((i) => i.id !== "A"));
    expect(out).toEqual([{ id: "B", x: 0, y: 0, w: 6, h: 4 }]);
  });

  it("Keyboard resize respects the minimum: Shift+Left at minimum width changes nothing", () => {
    const timingMin = { w: 4, h: 4 };
    const items = [{ id: "t", x: 0, y: 0, w: 4, h: 6 }];
    const out = resizeItem(items, "t", 3, 6, timingMin);
    expect(out[0]).toMatchObject({ w: 4, h: 6 });
  });

  it("clamps to 12 columns and the type minimum", () => {
    expect(clampRect({ x: 10, y: -3, w: 5, h: 1 }, MIN)).toEqual({ x: 7, y: 0, w: 5, h: 2 });
    expect(clampRect({ x: Number.NaN, y: 2.6, w: 40, h: 3 }, MIN)).toEqual({ x: 0, y: 3, w: 12, h: 3 });
  });

  it("resizing past the right edge stops at column 12", () => {
    const out = resizeItem([{ id: "a", x: 8, y: 0, w: 3, h: 3 }], "a", 6, 3, MIN);
    expect(out[0]).toMatchObject({ x: 8, w: 4 });
  });

  it("keeps widgets side by side and fills gaps upward", () => {
    const items = [
      { id: "L", x: 0, y: 0, w: 6, h: 4 },
      { id: "R", x: 6, y: 5, w: 6, h: 2 },
      { id: "U", x: 0, y: 9, w: 12, h: 2 },
    ];
    const out = compact(items);
    expect(out.map((i) => [i.id, i.y])).toEqual([
      ["L", 0],
      ["R", 0],
      ["U", 4],
    ]);
  });

  it("converts cells to pixels and pointer moves to cells", () => {
    const col = columnWidth(1228); // (1228 - 88) / 12 = 95
    expect(col).toBe(95);
    expect(toPixels({ x: 1, y: 2, w: 2, h: 3 }, col)).toEqual({ left: 103, top: 104, width: 198, height: 148 });
    expect(cellDelta(110, -60, col)).toEqual({ dx: 1, dy: -1 });
  });
});
