import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "../App";
import { parseStored, STORAGE_KEY, STORAGE_UNAVAILABLE, STORAGE_UNREADABLE } from "../canvas/persistence";
import { fakeBackend } from "../test/fakeBackend";
import { waitForShown } from "../test/renderApp";

async function open() {
  const view = render(<App />);
  await waitForShown(1);
  return view;
}

/** Unmounts and renders a fresh app, like a page reload (localStorage stays). */
async function reload(view: { unmount: () => void }) {
  view.unmount();
  return open();
}

function menu() {
  fireEvent.click(screen.getByRole("button", { name: "Board menu" }));
  return within(screen.getByRole("menu", { name: "Board menu" }));
}

function label() {
  return screen.getByTestId("board-menu-label");
}

function onlyWidget() {
  const widgets = screen.getAllByTestId("widget");
  expect(widgets).toHaveLength(1);
  return widgets[0];
}

describe("Board persistence", () => {
  it("Reload keeps a custom board: Board 1 with a lapchart pinned to PIA at (6,0) size 6×5", async () => {
    fakeBackend();
    let view = await open();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    fireEvent.click(menu().getByRole("menuitem", { name: "New blank board" }));
    fireEvent.click(screen.getByRole("button", { name: "Add widget" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Lap times" }));
    const title = within(onlyWidget()).getByTestId("widget-title");
    fireEvent.keyDown(title, { key: "ArrowLeft", shiftKey: true }); // 7 → 6 columns
    for (let i = 0; i < 6; i++) fireEvent.keyDown(within(onlyWidget()).getByTestId("widget-title"), { key: "ArrowRight" });
    fireEvent.change(within(onlyWidget()).getByRole("combobox"), { target: { value: "PIA" } });
    expect(onlyWidget()).toHaveAttribute("data-cell", "6,0,6,5");

    await waitFor(() => expect(localStorage.getItem(STORAGE_KEY)).toContain('"driver":"PIA"'));
    view = await reload(view);
    expect(label()).toHaveTextContent("Board 1");
    expect(onlyWidget()).toHaveAttribute("data-cell", "6,0,6,5");
    expect(onlyWidget()).toHaveAttribute("data-widget-type", "lapchart");
    expect(within(onlyWidget()).getByRole("combobox")).toHaveValue("PIA");
    view.unmount();
  });

  it("saves within 300 ms of a change, in the documented shape", async () => {
    fakeBackend();
    await open();
    fireEvent.click(menu().getByRole("menuitem", { name: "New blank board" }));
    const start = Date.now();
    await waitFor(() => expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull(), { interval: 10 });
    expect(Date.now() - start).toBeLessThan(600); // 300 ms debounce plus test scheduling slack
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
    expect(Object.keys(stored).sort()).toEqual(["activeBoardId", "customBoards", "presetEdits", "version"]);
    expect(stored.version).toBe(1);
    expect(stored.customBoards[0]).toMatchObject({ name: "Board 1", presetId: null, widgets: [] });
  });

  it("Reset an edited preset survives a reload until it is reset", async () => {
    fakeBackend();
    let view = await open();
    fireEvent.click(menu().getByRole("menuitemradio", { name: /PIT WALL/ }));
    fireEvent.click(screen.getByRole("button", { name: "Remove Timing widget" }));
    await waitFor(() => expect(localStorage.getItem(STORAGE_KEY)).toContain('"pit"'));
    view = await reload(view);
    expect(label()).toHaveTextContent(/PIT WALL\s*edited/);
    expect(screen.getAllByTestId("widget")).toHaveLength(3);
    fireEvent.click(menu().getByRole("menuitem", { name: "Reset to preset" }));
    expect(screen.getAllByTestId("widget")).toHaveLength(4);
    expect(label()).not.toHaveTextContent("edited");
    view.unmount();
  });

  it("Corrupted storage: presets load with the notice and the stored value is unchanged", async () => {
    fakeBackend();
    localStorage.setItem(STORAGE_KEY, "{not json");
    await open();
    expect(screen.getByTestId("storage-notice")).toHaveTextContent(STORAGE_UNREADABLE);
    expect(label()).toHaveTextContent("BATTLE");
    await new Promise((r) => setTimeout(r, 400));
    expect(localStorage.getItem(STORAGE_KEY)).toBe("{not json");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByTestId("storage-notice")).not.toBeInTheDocument();
  });

  it("a first visit with nothing stored starts on BATTLE without a notice", async () => {
    fakeBackend();
    await open();
    expect(label()).toHaveTextContent("BATTLE");
    expect(screen.queryByTestId("storage-notice")).not.toBeInTheDocument();
    expect(screen.queryByTestId("notice")).not.toBeInTheDocument();
  });

  it("storage that throws keeps boards in memory and says they will not be saved", async () => {
    fakeBackend();
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    await open();
    expect(screen.getByTestId("storage-notice")).toHaveTextContent(STORAGE_UNAVAILABLE);
    fireEvent.click(menu().getByRole("menuitem", { name: "New blank board" }));
    expect(label()).toHaveTextContent("Board 1");
    await new Promise((r) => setTimeout(r, 400));
    expect(setItem).not.toHaveBeenCalledWith(STORAGE_KEY, expect.anything());
  });

  it("a save that throws shows the notice", async () => {
    fakeBackend();
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("full", "QuotaExceededError");
    });
    await open();
    fireEvent.click(menu().getByRole("menuitem", { name: "New blank board" }));
    expect(await screen.findByTestId("storage-notice")).toHaveTextContent(STORAGE_UNAVAILABLE);
  });
});

describe("parseStored", () => {
  it("rejects other versions and malformed boards", () => {
    const ok = { version: 1, activeBoardId: "battle", presetEdits: {}, customBoards: [] };
    expect(parseStored(JSON.stringify(ok))).toEqual({ activeBoardId: "battle", presetEdits: {}, customBoards: [] });
    expect(parseStored(JSON.stringify({ ...ok, version: 2 }))).toBeNull();
    expect(parseStored(JSON.stringify({ ...ok, customBoards: [{ id: "x", name: "", widgets: [] }] }))).toBeNull();
    expect(parseStored("null")).toBeNull();
  });

  it("falls back to BATTLE when the active id is unknown and keeps gaps in stored positions", () => {
    const board = { id: "b1", name: "B", widgets: [{ id: "t", type: "timeline", x: 0, y: 5, w: 12, h: 2, settings: {} }] };
    const s = parseStored(JSON.stringify({ version: 1, activeBoardId: "gone", presetEdits: {}, customBoards: [board] }))!;
    expect(s.activeBoardId).toBe("battle");
    expect(s.customBoards[0].widgets[0]).toMatchObject({ x: 0, y: 5 });
  });
});
