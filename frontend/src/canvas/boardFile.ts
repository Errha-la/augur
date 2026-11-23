import type { Board, WidgetInstance } from "./board";
import { sanitizeName, sanitizeWidgets } from "./sanitize";

// Board files: `augur-board-<slug>.json` holding {format, version, board}.
// Imports are untrusted: size-limited, shape-checked, and sanitized.

export const BOARD_FILE_FORMAT = "augur-board";
export const BOARD_FILE_VERSION = 1;
export const MAX_FILE_BYTES = 100 * 1024;
export const NOT_A_BOARD_FILE = "Not an AUGUR board file.";

export interface BoardFile {
  format: typeof BOARD_FILE_FORMAT;
  version: typeof BOARD_FILE_VERSION;
  board: { name: string; widgets: WidgetInstance[] };
}

export function slug(name: string): string {
  return (
    name
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 40) || "board"
  );
}

export function exportBoard(board: Board): { fileName: string; text: string } {
  const file: BoardFile = {
    format: BOARD_FILE_FORMAT,
    version: BOARD_FILE_VERSION,
    board: { name: board.name, widgets: board.widgets },
  };
  return { fileName: `augur-board-${slug(board.name)}.json`, text: JSON.stringify(file, null, 2) };
}

export type ImportResult =
  | { ok: true; board: { name: string; widgets: WidgetInstance[] }; skipped: number }
  | { ok: false; message: typeof NOT_A_BOARD_FILE };

const REJECT = { ok: false, message: NOT_A_BOARD_FILE } as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Parses a board file's text; `bytes` is the file size (checked before parsing). */
export function parseBoardFile(text: string, bytes: number = new Blob([text]).size): ImportResult {
  if (bytes > MAX_FILE_BYTES) return REJECT;
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return REJECT;
  }
  if (!isRecord(raw) || raw.format !== BOARD_FILE_FORMAT || raw.version !== BOARD_FILE_VERSION) return REJECT;
  const board = raw.board;
  if (!isRecord(board) || !Array.isArray(board.widgets)) return REJECT;
  const name = sanitizeName(board.name);
  if (!name) return REJECT;
  const { widgets, skipped } = sanitizeWidgets(board.widgets);
  return { ok: true, board: { name, widgets }, skipped };
}

export function importReport(name: string, widgets: number, skipped: number): string {
  return `Imported ${name}: ${widgets} widgets, ${skipped} skipped`;
}
