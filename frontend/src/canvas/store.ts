import { type Board, type PresetId, sameBoard } from "./board";
import { DEFAULT_BOARD_ID, isPresetId, preset, PRESET_IDS } from "./presets";
import { sanitizeName } from "./sanitize";

// The viewer's boards: three presets (built-in or an edited copy) and any
// number of custom boards, one of them active ("Presets and custom boards").

export interface BoardsState {
  activeBoardId: string;
  presetEdits: Partial<Record<PresetId, Board>>;
  customBoards: Board[];
}

export { MAX_NAME_LENGTH } from "./sanitize";

export function initialBoards(): BoardsState {
  return { activeBoardId: DEFAULT_BOARD_ID, presetEdits: {}, customBoards: [] };
}

export function presetBoard(state: BoardsState, id: PresetId): Board {
  return state.presetEdits[id] ?? preset(id);
}

/** Presets first (in menu order), then custom boards. */
export function allBoards(state: BoardsState): Board[] {
  return [...PRESET_IDS.map((id) => presetBoard(state, id)), ...state.customBoards];
}

export function activeBoard(state: BoardsState): Board {
  return allBoards(state).find((b) => b.id === state.activeBoardId) ?? presetBoard(state, DEFAULT_BOARD_ID);
}

export function isEdited(state: BoardsState, id: string): boolean {
  return isPresetId(id) && state.presetEdits[id] !== undefined;
}

/** "Board <n>" with the lowest n not used by any board name. */
export function nextBoardName(state: BoardsState): string {
  const names = new Set(allBoards(state).map((b) => b.name));
  let n = 1;
  while (names.has(`Board ${n}`)) n++;
  return `Board ${n}`;
}

let idCounter = 0;
/** A board id unique within this state (custom boards only; presets use their preset id). */
export function newBoardId(state: BoardsState): string {
  const used = new Set(allBoards(state).map((b) => b.id));
  let id: string;
  do id = `board-${Date.now().toString(36)}-${(idCounter++).toString(36)}`;
  while (used.has(id));
  return id;
}

function cleanName(name: string): string {
  return sanitizeName(name) ?? "";
}

export type BoardsAction =
  | { type: "select"; id: string }
  | { type: "update"; update: Board | ((board: Board) => Board) }
  | { type: "newBlank" }
  | { type: "rename"; id: string; name: string }
  | { type: "duplicate"; id: string }
  | { type: "delete"; id: string }
  | { type: "reset"; id: PresetId }
  | { type: "add"; board: Omit<Board, "id" | "presetId"> };

/** Stores `board` (a preset edit or a custom board) in place. */
function put(state: BoardsState, board: Board): BoardsState {
  if (board.presetId !== null) {
    const pid = board.presetId;
    const presetEdits = { ...state.presetEdits };
    if (sameBoard(board, preset(pid))) delete presetEdits[pid];
    else presetEdits[pid] = { ...board, id: pid };
    return { ...state, presetEdits };
  }
  return { ...state, customBoards: state.customBoards.map((b) => (b.id === board.id ? board : b)) };
}

function addCustom(state: BoardsState, board: Omit<Board, "id" | "presetId">): BoardsState {
  const created: Board = { ...structuredClone(board), id: newBoardId(state), presetId: null };
  return { ...state, customBoards: [...state.customBoards, created], activeBoardId: created.id };
}

export function boardsReducer(state: BoardsState, action: BoardsAction): BoardsState {
  switch (action.type) {
    case "select":
      return allBoards(state).some((b) => b.id === action.id) ? { ...state, activeBoardId: action.id } : state;
    case "update": {
      const current = activeBoard(state);
      const next = typeof action.update === "function" ? action.update(current) : action.update;
      if (next === current) return state;
      return put(state, { ...next, id: current.id, presetId: current.presetId });
    }
    case "newBlank":
      return addCustom(state, { name: nextBoardName(state), widgets: [] });
    case "rename": {
      const board = allBoards(state).find((b) => b.id === action.id);
      const name = cleanName(action.name);
      if (!board || !name || name === board.name) return state;
      return put(state, { ...board, name });
    }
    case "duplicate": {
      const board = allBoards(state).find((b) => b.id === action.id);
      if (!board) return state;
      return addCustom(state, { name: cleanName(`${board.name} copy`), widgets: board.widgets });
    }
    case "delete": {
      if (!state.customBoards.some((b) => b.id === action.id)) return state; // presets cannot be deleted
      return {
        ...state,
        customBoards: state.customBoards.filter((b) => b.id !== action.id),
        activeBoardId: state.activeBoardId === action.id ? DEFAULT_BOARD_ID : state.activeBoardId,
      };
    }
    case "reset": {
      const presetEdits = { ...state.presetEdits };
      delete presetEdits[action.id];
      return { ...state, presetEdits };
    }
    case "add":
      return addCustom(state, action.board);
  }
}
