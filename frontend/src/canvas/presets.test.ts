import { describe, expect, it } from "vitest";
import { collides, COLS } from "./grid";
import { preset, PRESET_IDS } from "./presets";
import { REGISTRY } from "./registry";

describe("presets", () => {
  it.each(PRESET_IDS)("%s has no overlaps, fits 12 columns, and respects type minimums", (id) => {
    const board = preset(id);
    expect(board.presetId).toBe(id);
    expect(new Set(board.widgets.map((w) => w.id)).size).toBe(board.widgets.length);
    for (const w of board.widgets) {
      expect(w.x + w.w).toBeLessThanOrEqual(COLS);
      expect(w.w).toBeGreaterThanOrEqual(REGISTRY[w.type].minSize.w);
      expect(w.h).toBeGreaterThanOrEqual(REGISTRY[w.type].minSize.h);
      for (const o of board.widgets) if (o !== w) expect(collides(w, o)).toBe(false);
    }
  });

  it("matches the design table", () => {
    const pos = (id: (typeof PRESET_IDS)[number]) => preset(id).widgets.map((w) => [w.type, w.x, w.y, w.w, w.h]);
    expect(preset("pit").name).toBe("PIT WALL");
    expect(pos("pit")).toEqual([
      ["driver", 0, 0, 5, 9],
      ["events", 5, 0, 7, 6],
      ["lapchart", 5, 6, 7, 5],
      ["timing", 0, 9, 5, 6],
    ]);
    expect(pos("battle")).toEqual([
      ["timing", 0, 0, 5, 10],
      ["events", 5, 0, 7, 6],
      ["driver", 5, 6, 7, 7],
      ["timeline", 0, 13, 12, 2],
    ]);
    expect(pos("pace")).toEqual([
      ["lapchart", 0, 0, 8, 6],
      ["events", 8, 0, 4, 6],
      ["timing", 0, 6, 7, 8],
      ["driver", 7, 6, 5, 8],
    ]);
    expect(preset("battle").widgets[1].settings.types).toEqual(["position_change", "undercut_window", "overcut_window"]);
  });

  it("returns independent copies", () => {
    const a = preset("pace");
    a.widgets.pop();
    expect(preset("pace").widgets).toHaveLength(4);
  });
});
