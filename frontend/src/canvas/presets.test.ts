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
    // strategy-chart-widgets: one widget swapped in each existing preset, same place.
    expect(pos("pit")).toEqual([
      ["driver", 0, 0, 5, 9],
      ["events", 5, 0, 7, 6],
      ["pitwindow", 5, 6, 7, 5],
      ["timing", 0, 9, 5, 6],
    ]);
    expect(pos("battle")).toEqual([
      ["timing", 0, 0, 5, 10],
      ["events", 5, 0, 7, 6],
      ["trace", 5, 6, 7, 7],
      ["timeline", 0, 13, 12, 2],
    ]);
    expect(pos("pace")).toEqual([
      ["lapchart", 0, 0, 8, 6],
      ["events", 8, 0, 4, 6],
      ["timing", 0, 6, 7, 8],
      ["pace", 7, 6, 5, 8],
    ]);
    expect(preset("pit").widgets[2].settings).toEqual({ driver: null });
    expect(preset("pace").widgets[3].settings).toEqual({});
    // The design table's types, kept in EVENT_TYPES order (the chips' order).
    expect(preset("battle").widgets[1].settings.types).toEqual(["undercut_window", "overcut_window", "position_change"]);
    expect(preset("pace").widgets[1].settings.types).toEqual(["degradation_warning", "pace_drop"]);
  });

  it("STRATEGY preset: pit window and pit clock following the focus driver, stints, degradation, race trace", () => {
    expect(PRESET_IDS).toEqual(["pit", "battle", "pace", "strategy"]);
    const board = preset("strategy");
    expect(board.name).toBe("STRATEGY");
    expect(board.widgets.map((w) => [w.type, w.x, w.y, w.w, w.h, w.settings])).toEqual([
      ["pitwindow", 0, 0, 7, 6, { driver: null }],
      ["pitclock", 7, 0, 5, 6, { driver: null }],
      ["stints", 0, 6, 7, 7, {}],
      ["degradation", 7, 6, 5, 7, {}],
      ["trace", 0, 13, 12, 6, {}],
    ]);
  });

  it("returns independent copies", () => {
    const a = preset("pace");
    a.widgets.pop();
    expect(preset("pace").widgets).toHaveLength(4);
  });
});
