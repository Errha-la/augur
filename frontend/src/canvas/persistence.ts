import type { Board, PresetId } from "./board";
import { isPresetId, PRESET_IDS } from "./presets";
import { sanitizeName, sanitizeWidgets } from "./sanitize";
import { allBoards, type BoardsState, initialBoards } from "./store";

// Boards in localStorage ("Boards in localStorage with JSON export and import").

export const STORAGE_KEY = "augur.boards.v1";
export const STORAGE_UNREADABLE = "Saved boards could not be read; started from the presets.";
export const STORAGE_UNAVAILABLE = "Boards will not be saved in this browser.";
export const SAVE_DELAY_MS = 300;

interface StoredBoards extends BoardsState {
  version: 1;
}

export interface LoadedBoards {
  state: BoardsState;
  notice: string | null;
  /** False when storage throws: boards stay in memory for the page. */
  canSave: boolean;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const CUSTOM_ID = /^[A-Za-z0-9_-]{1,64}$/;

function parseBoard(raw: unknown, presetId: PresetId | null): Board | null {
  if (!isRecord(raw)) return null;
  const name = sanitizeName(raw.name);
  const id = presetId ?? (typeof raw.id === "string" && CUSTOM_ID.test(raw.id) && !isPresetId(raw.id) ? raw.id : null);
  if (!name || !id || !Array.isArray(raw.widgets)) return null;
  return { id, name, presetId, widgets: sanitizeWidgets(raw.widgets).widgets };
}

/** The stored value as boards, or null when it is not a version-1 boards value. */
export function parseStored(text: string): BoardsState | null {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return null;
  }
  if (!isRecord(raw) || raw.version !== 1 || !isRecord(raw.presetEdits) || !Array.isArray(raw.customBoards)) return null;
  const presetEdits: BoardsState["presetEdits"] = {};
  for (const id of PRESET_IDS) {
    if (raw.presetEdits[id] === undefined) continue;
    const board = parseBoard(raw.presetEdits[id], id);
    if (!board) return null;
    presetEdits[id] = board;
  }
  const customBoards: Board[] = [];
  for (const entry of raw.customBoards) {
    const board = parseBoard(entry, null);
    if (!board || customBoards.some((b) => b.id === board.id)) return null;
    customBoards.push(board);
  }
  const state: BoardsState = { activeBoardId: initialBoards().activeBoardId, presetEdits, customBoards };
  if (typeof raw.activeBoardId === "string" && allBoards(state).some((b) => b.id === raw.activeBoardId)) {
    state.activeBoardId = raw.activeBoardId;
  }
  return state;
}

export function loadBoards(storage: () => Storage = () => window.localStorage): LoadedBoards {
  let text: string | null;
  try {
    text = storage().getItem(STORAGE_KEY);
  } catch {
    return { state: initialBoards(), notice: STORAGE_UNAVAILABLE, canSave: false };
  }
  // Nothing saved yet (a first visit): start from the presets without a notice.
  if (text === null) return { state: initialBoards(), notice: null, canSave: true };
  const state = parseStored(text);
  if (!state) return { state: initialBoards(), notice: STORAGE_UNREADABLE, canSave: true };
  return { state, notice: null, canSave: true };
}

export function serialize(state: BoardsState): string {
  const stored: StoredBoards = {
    version: 1,
    activeBoardId: state.activeBoardId,
    presetEdits: state.presetEdits,
    customBoards: state.customBoards,
  };
  return JSON.stringify(stored);
}

/** Saves boards; false when storage throws (private mode, blocked, full). */
export function saveBoards(state: BoardsState, storage: () => Storage = () => window.localStorage): boolean {
  try {
    storage().setItem(STORAGE_KEY, serialize(state));
    return true;
  } catch {
    return false;
  }
}
