import { type Dispatch, type FormEvent, type ReactNode, useState } from "react";
import { isPresetId } from "../canvas/presets";
import { activeBoard, allBoards, type BoardsAction, type BoardsState, isEdited, MAX_NAME_LENGTH } from "../canvas/store";
import { Menu, menuButton, menuItem } from "./Menu";

interface BoardMenuProps {
  state: BoardsState;
  dispatch: Dispatch<BoardsAction>;
  /** Export and Import entries (added by the caller). */
  fileActions?: (close: () => void) => ReactNode;
}

function EditedMark() {
  return <span className="ml-1 text-[10px] font-normal tracking-wider text-flag-yellow">edited</span>;
}

/** Board switcher and board actions in the status bar. */
export function BoardMenu({ state, dispatch, fileActions }: BoardMenuProps) {
  const active = activeBoard(state);
  return (
    <Menu
      ariaLabel="Board menu"
      guide="board-menu"
      label={
        <span data-testid="board-menu-label">
          <span className="text-zinc-500">BOARD </span>
          <span className="font-bold text-zinc-100">{active.name}</span>
          {isEdited(state, active.id) && <EditedMark />}
          <span aria-hidden className="ml-1 text-zinc-500">
            ▾
          </span>
        </span>
      }
    >
      {(close) => <BoardMenuBody state={state} dispatch={dispatch} close={close} fileActions={fileActions} />}
    </Menu>
  );
}

function BoardMenuBody({ state, dispatch, close, fileActions }: BoardMenuProps & { close: () => void }) {
  const [mode, setMode] = useState<"list" | "rename" | "delete">("list");
  const active = activeBoard(state);
  const [name, setName] = useState(active.name);
  const act = (action: BoardsAction) => {
    dispatch(action);
    close();
  };

  if (mode === "rename") {
    const submit = (e: FormEvent) => {
      e.preventDefault();
      act({ type: "rename", id: active.id, name });
    };
    return (
      <form onSubmit={submit} className="flex flex-col gap-2 p-1">
        <label className="text-xs text-zinc-400">
          Board name
          <input
            autoFocus
            aria-label="Board name"
            maxLength={MAX_NAME_LENGTH}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 block w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm text-zinc-100"
          />
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" className={menuButton} onClick={() => setMode("list")}>
            Cancel
          </button>
          <button type="submit" className={menuButton} disabled={!name.trim()}>
            Save
          </button>
        </div>
      </form>
    );
  }

  if (mode === "delete") {
    return (
      <div role="alertdialog" aria-label="Confirm delete" className="flex flex-col gap-2 p-1">
        <p className="text-sm text-zinc-200">Delete {active.name}? This cannot be undone.</p>
        <div className="flex justify-end gap-2">
          <button type="button" autoFocus className={menuButton} onClick={() => setMode("list")}>
            Cancel
          </button>
          <button
            type="button"
            className={`${menuButton} border-flag-red/60 text-flag-red`}
            onClick={() => act({ type: "delete", id: active.id })}
          >
            Delete
          </button>
        </div>
      </div>
    );
  }

  const custom = active.presetId === null;
  const editedPreset = isPresetId(active.id) && isEdited(state, active.id) ? active.id : null;
  return (
    <div className="flex max-h-[70vh] flex-col overflow-auto">
      <div role="group" aria-label="Boards">
        {allBoards(state).map((b) => (
          <button
            key={b.id}
            type="button"
            role="menuitemradio"
            aria-checked={b.id === active.id}
            className={`${menuItem} ${b.id === active.id ? "font-bold text-zinc-50" : ""}`}
            onClick={() => act({ type: "select", id: b.id })}
          >
            <span aria-hidden className="inline-block w-4">
              {b.id === active.id ? "●" : ""}
            </span>
            {b.name}
            {isEdited(state, b.id) && <EditedMark />}
          </button>
        ))}
      </div>
      <hr className="my-1 border-zinc-800" />
      <button type="button" role="menuitem" className={menuItem} onClick={() => act({ type: "newBlank" })}>
        New blank board
      </button>
      <button type="button" role="menuitem" className={menuItem} onClick={() => setMode("rename")}>
        Rename
      </button>
      <button type="button" role="menuitem" className={menuItem} onClick={() => act({ type: "duplicate", id: active.id })}>
        Duplicate
      </button>
      {editedPreset && (
        <button type="button" role="menuitem" className={menuItem} onClick={() => act({ type: "reset", id: editedPreset })}>
          Reset to preset
        </button>
      )}
      {custom && (
        <button type="button" role="menuitem" className={menuItem} onClick={() => setMode("delete")}>
          Delete
        </button>
      )}
      {fileActions && (
        <>
          <hr className="my-1 border-zinc-800" />
          {fileActions(close)}
        </>
      )}
    </div>
  );
}
