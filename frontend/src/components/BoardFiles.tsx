import { useRef } from "react";
import type { Board } from "../canvas/board";
import { exportBoard, importReport, MAX_FILE_BYTES, NOT_A_BOARD_FILE, parseBoardFile } from "../canvas/boardFile";
import { menuItem } from "./Menu";

function download(text: string, fileName: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoke after the click has handed the blob to the download.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

interface BoardFilesProps {
  board: Board;
  onImport: (board: { name: string; widgets: Board["widgets"] }) => void;
  onMessage: (text: string) => void;
}

/**
 * Export and Import entries for the board menu, plus the hidden file input
 * (kept outside the menu so it survives the menu closing).
 */
export function useBoardFiles({ board, onImport, onMessage }: BoardFilesProps) {
  const input = useRef<HTMLInputElement>(null);

  const importFile = async (file: File) => {
    // Checked before reading, so an oversized file is never loaded.
    if (file.size > MAX_FILE_BYTES) {
      onMessage(NOT_A_BOARD_FILE);
      return;
    }
    const result = parseBoardFile(await file.text(), file.size);
    if (!result.ok) {
      onMessage(result.message);
      return;
    }
    onImport(result.board);
    onMessage(importReport(result.board.name, result.board.widgets.length, result.skipped));
  };

  const fileInput = (
    <input
      ref={input}
      type="file"
      accept=".json,application/json"
      aria-label="Import board file"
      data-testid="board-import"
      className="hidden"
      onChange={(e) => {
        const file = e.target.files?.[0];
        e.target.value = ""; // the same file can be imported again
        if (file) void importFile(file);
      }}
    />
  );

  const menuItems = (close: () => void) => (
    <>
      <button
        type="button"
        role="menuitem"
        className={menuItem}
        onClick={() => {
          close();
          const { fileName, text } = exportBoard(board);
          download(text, fileName);
        }}
      >
        Export
      </button>
      <button
        type="button"
        role="menuitem"
        className={menuItem}
        onClick={() => {
          close();
          input.current?.click();
        }}
      >
        Import
      </button>
    </>
  );

  return { fileInput, menuItems };
}
