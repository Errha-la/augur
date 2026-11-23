import type { Board, PresetId, WidgetInstance, WidgetSettings, WidgetType } from "./board";
import { EVENT_TYPES } from "./registry";

// Built-in boards from the design's presets table ("Presets and custom boards").

type Spec = [WidgetType, x: number, y: number, w: number, h: number, settings?: WidgetSettings];

/**
 * Event types in EVENT_TYPES order, the order the type chips and the sanitizer
 * produce, so a preset whose chips are toggled back compares equal to the
 * built-in and loses its "edited" mark.
 */
function normalized(settings: WidgetSettings): WidgetSettings {
  const { types } = settings;
  return types ? { ...settings, types: EVENT_TYPES.filter((t) => types.includes(t)) } : settings;
}

function board(id: PresetId, name: string, specs: Spec[]): Board {
  const counts: Partial<Record<WidgetType, number>> = {};
  const widgets: WidgetInstance[] = specs.map(([type, x, y, w, h, settings = {}]) => {
    const n = (counts[type] = (counts[type] ?? 0) + 1);
    return { id: `${type}-${n}`, type, x, y, w, h, settings: normalized(settings) };
  });
  return { id, name, presetId: id, widgets };
}

const PRESETS: Record<PresetId, Board> = {
  pit: board("pit", "PIT WALL", [
    ["driver", 0, 0, 5, 9, { driver: null }],
    ["events", 5, 0, 7, 6, { types: ["degradation_warning", "undercut_window", "overcut_window"] }],
    ["lapchart", 5, 6, 7, 5, { driver: null }],
    ["timing", 0, 9, 5, 6],
  ]),
  battle: board("battle", "BATTLE", [
    ["timing", 0, 0, 5, 10],
    ["events", 5, 0, 7, 6, { types: ["position_change", "undercut_window", "overcut_window"] }],
    ["driver", 5, 6, 7, 7, { driver: null }],
    ["timeline", 0, 13, 12, 2],
  ]),
  pace: board("pace", "PACE", [
    ["lapchart", 0, 0, 8, 6, { driver: null }],
    ["events", 8, 0, 4, 6, { types: ["pace_drop", "degradation_warning"] }],
    ["timing", 0, 6, 7, 8],
    ["driver", 7, 6, 5, 8, { driver: null }],
  ]),
};

export const PRESET_IDS: PresetId[] = ["pit", "battle", "pace"];
/** The board shown on a first visit and after deleting the active board. */
export const DEFAULT_BOARD_ID: PresetId = "battle";

/** A fresh copy of a built-in preset (callers may edit it freely). */
export function preset(id: PresetId): Board {
  return structuredClone(PRESETS[id]);
}

export function isPresetId(value: unknown): value is PresetId {
  return value === "pit" || value === "battle" || value === "pace";
}
