import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "../App";
import { exportBoard, MAX_FILE_BYTES, NOT_A_BOARD_FILE, parseBoardFile, slug } from "../canvas/boardFile";
import { STORAGE_UNAVAILABLE } from "../canvas/persistence";
import { activeBoard } from "../canvas/store";
import { fakeBackend } from "../test/fakeBackend";
import { waitForShown } from "../test/renderApp";

async function open() {
  fakeBackend();
  render(<App />);
  await waitForShown(1);
}

function menuItem(name: string) {
  fireEvent.click(screen.getByRole("button", { name: "Board menu" }));
  return within(screen.getByRole("menu", { name: "Board menu" })).getByRole("menuitem", { name });
}

function boardNames() {
  fireEvent.click(screen.getByRole("button", { name: "Board menu" }));
  const names = within(screen.getByRole("menu", { name: "Board menu" }))
    .getAllByRole("menuitemradio")
    .map((b) => b.textContent?.replace("●", ""));
  fireEvent.keyDown(document, { key: "Escape" });
  return names;
}

function importText(text: string, name = "board.json") {
  const file = new File([text], name, { type: "application/json" });
  fireEvent.change(screen.getByTestId("board-import"), { target: { files: [file] } });
}

function cells() {
  return screen.getAllByTestId("widget").map((w) => [w.dataset.widgetType, w.dataset.cell]);
}

function fileWith(widgets: unknown[], name = "Shared") {
  return JSON.stringify({ format: "augur-board", version: 1, board: { name, widgets } });
}

describe("Board export and import", () => {
  it("Round trip: exporting then importing adds an identical custom board and makes it active", async () => {
    await open();
    // Make the board differ from the preset: pin the driver widget.
    fireEvent.change(screen.getByRole("combobox", { name: "Driver for Driver widget" }), { target: { value: "PIA" } });
    const before = cells();

    let blob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((b) => {
      blob = b as Blob;
      return "blob:test";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const clicks: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicks.push(this.download);
    });
    fireEvent.click(menuItem("Export"));
    expect(clicks).toEqual(["augur-board-battle.json"]);
    const text = await blob!.text();
    expect(JSON.parse(text)).toMatchObject({ format: "augur-board", version: 1, board: { name: "BATTLE" } });

    importText(text);
    expect(await screen.findByTestId("notice")).toHaveTextContent("Imported BATTLE: 4 widgets, 0 skipped");
    expect(screen.getByTestId("board-menu-label")).toHaveTextContent("BATTLE");
    expect(cells()).toEqual(before);
    expect(screen.getByRole("combobox", { name: "Driver for Driver widget" })).toHaveValue("PIA");
    expect(boardNames()).toEqual(["PIT WALL", "BATTLEedited", "PACE", "BATTLE"]);
  });

  it("Unknown widget type: timing, lapchart and heatmap3d import as 2 widgets, 1 skipped", async () => {
    await open();
    importText(
      fileWith([
        { id: "a", type: "timing", x: 0, y: 0, w: 5, h: 10, settings: {} },
        { id: "b", type: "lapchart", x: 5, y: 0, w: 7, h: 5, settings: { driver: "LEC" } },
        { id: "c", type: "heatmap3d", x: 0, y: 10, w: 12, h: 4, settings: {} },
      ]),
    );
    expect(await screen.findByTestId("notice")).toHaveTextContent("Imported Shared: 2 widgets, 1 skipped");
    expect(screen.getByTestId("board-menu-label")).toHaveTextContent("Shared");
    expect(cells()).toEqual([
      ["timing", "0,0,5,10"],
      ["lapchart", "5,0,7,5"],
    ]);
  });

  it("Wrong file: {\"format\": \"other\"} is rejected and no board is added", async () => {
    await open();
    importText('{"format": "other"}');
    expect(await screen.findByTestId("notice")).toHaveTextContent(NOT_A_BOARD_FILE);
    expect(boardNames()).toEqual(["PIT WALL", "BATTLE", "PACE"]);
  });

  it("an import report does not hide 'Boards will not be saved in this browser.'", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    await open();
    importText(fileWith([{ id: "a", type: "timing", x: 0, y: 0, w: 5, h: 10, settings: {} }]));
    expect(await screen.findByTestId("notice")).toHaveTextContent("Imported Shared: 1 widgets, 0 skipped");
    expect(screen.getByTestId("storage-notice")).toHaveTextContent(STORAGE_UNAVAILABLE);
  });

  it("a 101 KB file is rejected before it is read", async () => {
    await open();
    const big = fileWith([], "Big").replace('"Big"', `"Big", "pad": "${"x".repeat(101 * 1024)}"`);
    expect(big.length).toBeGreaterThan(MAX_FILE_BYTES);
    const text = vi.spyOn(File.prototype, "text");
    importText(big);
    expect(await screen.findByTestId("notice")).toHaveTextContent(NOT_A_BOARD_FILE);
    expect(text).not.toHaveBeenCalled();
    expect(boardNames()).toEqual(["PIT WALL", "BATTLE", "PACE"]);
  });

  it("an imported board is saved like any other board", async () => {
    await open();
    importText(fileWith([{ type: "timeline", x: 0, y: 0, w: 12, h: 2 }], "Saved"));
    await waitFor(() => expect(localStorage.getItem("augur.boards.v1")).toContain('"name":"Saved"'));
  });
});

describe("parseBoardFile", () => {
  it("clamps geometry, resolves overlaps, sanitizes settings and caps at 24 widgets", () => {
    const widgets = [
      { id: "x", type: "events", x: 11, y: -2, w: 1, h: 1, settings: { types: ["pace_drop", "nope"], driver: "VER" } },
      { id: "x", type: "events", x: 9, y: 0, w: 3, h: 4, settings: {} },
      { id: "d", type: "driver", x: 0, y: 0, w: 4, h: 6, settings: { driver: "<img onerror=1>" } },
      ...Array.from({ length: 30 }, () => ({ type: "timeline", x: 0, y: 50, w: 12, h: 2 })),
    ];
    const r = parseBoardFile(fileWith(widgets, "  Mine \n board "));
    if (!r.ok) throw new Error("rejected");
    expect(r.board.name).toBe("Mine board");
    expect(r.board.widgets).toHaveLength(24);
    expect(r.skipped).toBe(33 - 24);
    const [e1, e2, d] = r.board.widgets;
    expect(e1).toMatchObject({ id: "x", x: 9, y: 0, w: 3, h: 4, settings: { types: ["pace_drop"] } });
    expect(e1.settings).not.toHaveProperty("driver");
    expect(e2).toMatchObject({ id: "events-1", y: 4 });
    expect(d.settings.driver).toBeNull();
  });

  it("import keeps a gap in the file instead of compacting it upward", () => {
    const r = parseBoardFile(
      fileWith([
        { id: "t", type: "timing", x: 0, y: 0, w: 5, h: 6, settings: {} },
        { id: "l", type: "timeline", x: 0, y: 12, w: 12, h: 2, settings: {} },
        { id: "d", type: "driver", x: 2, y: 4, w: 5, h: 4, settings: {} },
      ]),
    );
    if (!r.ok) throw new Error("rejected");
    const [t, l, d] = r.board.widgets;
    expect(t).toMatchObject({ x: 0, y: 0 });
    // The overlapping driver widget is pushed down, never up...
    expect(d).toMatchObject({ x: 2, y: 6 });
    // ...and the timeline keeps its row 12 instead of compacting up to row 10.
    expect(l).toMatchObject({ x: 0, y: 12 });
  });

  it("rejects files with another version, no board, or a missing name", () => {
    const ok = JSON.parse(fileWith([]));
    for (const bad of [{ ...ok, version: 2 }, { ...ok, board: null }, { ...ok, board: { name: " ", widgets: [] } }, "[]"]) {
      expect(parseBoardFile(typeof bad === "string" ? bad : JSON.stringify(bad))).toEqual({ ok: false, message: NOT_A_BOARD_FILE });
    }
  });

  it("names the export after the board", () => {
    expect(slug("PIT WALL")).toBe("pit-wall");
    expect(slug("  ★★ ")).toBe("board");
    const { fileName } = exportBoard(activeBoard({ activeBoardId: "pit", presetEdits: {}, customBoards: [] }));
    expect(fileName).toBe("augur-board-pit-wall.json");
  });
});
