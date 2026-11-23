import { describe, expect, it } from "vitest";
import { toggleType } from "../components/EventTypeChips";
import { type Board, removeWidget, updateSettings } from "./board";
import { preset, PRESET_IDS } from "./presets";
import { activeBoard, allBoards, type BoardsAction, boardsReducer, type BoardsState, initialBoards, isEdited } from "./store";

function run(...actions: BoardsAction[]): BoardsState {
  return actions.reduce(boardsReducer, initialBoards());
}

describe("boards store", () => {
  it("starts on BATTLE with the three presets", () => {
    const s = initialBoards();
    expect(activeBoard(s).name).toBe("BATTLE");
    expect(allBoards(s).map((b) => b.name)).toEqual(["PIT WALL", "BATTLE", "PACE"]);
  });

  it("editing a preset keeps the edited copy and marks it; reset restores the built-in", () => {
    let s = run({ type: "select", id: "pit" }, { type: "update", update: (b) => removeWidget(b, b.widgets[0].id) });
    expect(isEdited(s, "pit")).toBe(true);
    expect(activeBoard(s).widgets).toHaveLength(3);
    s = boardsReducer(s, { type: "reset", id: "pit" });
    expect(isEdited(s, "pit")).toBe(false);
    expect(activeBoard(s)).toEqual(preset("pit"));
  });

  it("an edit that returns a preset to its built-in definition clears the mark", () => {
    const s = run({ type: "rename", id: "pace", name: "Mine" }, { type: "rename", id: "pace", name: "PACE" });
    expect(isEdited(s, "pace")).toBe(false);
  });

  it.each(PRESET_IDS)("toggling an event-type chip off and on again clears the %s edited mark", (id) => {
    const events = preset(id).widgets.find((w) => w.type === "events")!;
    const flip = (b: Board) => {
      const w = b.widgets.find((x) => x.id === events.id)!;
      return updateSettings(b, w.id, { types: toggleType(w.settings.types, "position_change") });
    };
    let s = run({ type: "select", id }, { type: "update", update: flip });
    expect(isEdited(s, id)).toBe(true);
    s = boardsReducer(s, { type: "update", update: flip });
    expect(isEdited(s, id)).toBe(false);
  });

  it("Blank board: names use the lowest free number and become active", () => {
    let s = run({ type: "newBlank" });
    expect(activeBoard(s)).toMatchObject({ name: "Board 1", presetId: null, widgets: [] });
    s = boardsReducer(s, { type: "newBlank" });
    expect(activeBoard(s).name).toBe("Board 2");
    s = boardsReducer(s, { type: "delete", id: s.customBoards[0].id });
    s = boardsReducer(s, { type: "newBlank" });
    expect(activeBoard(s).name).toBe("Board 1");
  });

  it("duplicate makes a custom copy named '<name> copy'", () => {
    const s = run({ type: "duplicate", id: "battle" });
    const copy = activeBoard(s);
    expect(copy).toMatchObject({ name: "BATTLE copy", presetId: null });
    expect(copy.id).not.toBe("battle");
    expect(copy.widgets).toEqual(preset("battle").widgets);
  });

  it("Delete active board: the board is gone and BATTLE is active; presets cannot be deleted", () => {
    let s = run({ type: "newBlank" }, { type: "select", id: "pace" }, { type: "newBlank" });
    const id = s.activeBoardId;
    s = boardsReducer(s, { type: "delete", id });
    expect(s.customBoards.map((b) => b.id)).not.toContain(id);
    expect(s.activeBoardId).toBe("battle");
    expect(boardsReducer(s, { type: "delete", id: "pit" })).toBe(s);
  });

  it("rename trims, caps the length, and ignores empty names", () => {
    let s = run({ type: "newBlank" });
    const id = s.activeBoardId;
    s = boardsReducer(s, { type: "rename", id, name: "   " });
    expect(activeBoard(s).name).toBe("Board 1");
    s = boardsReducer(s, { type: "rename", id, name: `  ${"x".repeat(80)} ` });
    expect(activeBoard(s).name).toHaveLength(60);
  });
});
