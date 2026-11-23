import { type Dispatch, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { loadBoards, SAVE_DELAY_MS, saveBoards, STORAGE_UNAVAILABLE } from "../canvas/persistence";
import { type BoardsAction, boardsReducer, type BoardsState } from "../canvas/store";

export interface UseBoards {
  state: BoardsState;
  dispatch: Dispatch<BoardsAction>;
  /**
   * Storage state ("could not be read" / "will not be saved"). Kept apart from
   * `notice` so a later message (import report, board full) never hides it.
   */
  storageNotice: string | null;
  dismissStorageNotice: () => void;
  /** One-off messages: import reports, "A board holds at most 24 widgets". */
  notice: string | null;
  setNotice: (notice: string | null) => void;
}

/**
 * Boards loaded from localStorage once, saved SAVE_DELAY_MS after the last
 * change (and right away when the page is hidden). Nothing is written until the
 * viewer changes a board, so an unreadable stored value is kept until then.
 * `start` replaces the stored boards (tests).
 */
export function useBoards(start?: BoardsState): UseBoards {
  const [loaded] = useState(() => (start ? { state: start, notice: null, canSave: true } : loadBoards()));
  const [state, rawDispatch] = useReducer(boardsReducer, loaded.state);
  const [storageNotice, setStorageNotice] = useState<string | null>(loaded.notice);
  const [notice, setNotice] = useState<string | null>(null);
  const dismissStorageNotice = useCallback(() => setStorageNotice(null), []);
  const canSave = useRef(loaded.canSave);
  const unsaved = useRef(false);
  const latest = useRef(state);
  latest.current = state;

  const dispatch = useCallback((action: BoardsAction) => {
    unsaved.current = true;
    rawDispatch(action);
  }, []);

  const flush = useCallback(() => {
    if (!unsaved.current || !canSave.current) return;
    unsaved.current = false;
    if (!saveBoards(latest.current)) {
      canSave.current = false;
      setStorageNotice(STORAGE_UNAVAILABLE);
    }
  }, []);

  useEffect(() => {
    if (!unsaved.current) return;
    const timer = setTimeout(flush, SAVE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [state, flush]);

  useEffect(() => {
    const onHide = () => flush();
    window.addEventListener("pagehide", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      flush();
    };
  }, [flush]);

  return { state, dispatch, storageNotice, dismissStorageNotice, notice, setNotice };
}
