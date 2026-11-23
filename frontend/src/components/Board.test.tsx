import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import type { Board as BoardModel, WidgetInstance } from "../canvas/board";
import { columnWidth } from "../canvas/grid";
import { preset } from "../canvas/presets";
import { fakeBackend } from "../test/fakeBackend";
import App from "../App";
import { boardsWith, CLASSIC_BOARD, layout, renderApp, waitForShown } from "../test/renderApp";
import { BOARD_FULL } from "../canvas/board";
import { Board, EMPTY_BOARD } from "./Board";

// 1228 px wide: columns of 95 px plus 8 px gaps, so one column step is 103 px
// and one row step 52 px (44 px rows + 8 px gaps).
const WIDTH = 1228;
const COL_STEP = columnWidth(WIDTH) + 8;
const ROW_STEP = 52;

const AB: BoardModel = {
  id: "t",
  name: "Test",
  presetId: null,
  widgets: [
    { id: "A", type: "timeline", x: 0, y: 0, w: 6, h: 4, settings: {} },
    { id: "B", type: "timeline", x: 0, y: 4, w: 6, h: 4, settings: {} },
  ],
};

function Harness({ initial, onBoard }: { initial: BoardModel; onBoard?: (b: BoardModel) => void }) {
  const [board, setBoard] = useState(initial);
  return (
    <Board
      board={board}
      width={WIDTH}
      onChange={(b) => {
        setBoard(b);
        onBoard?.(b);
      }}
      renderWidget={(w: WidgetInstance) => ({ body: <p>body {w.id}</p> })}
    />
  );
}

function widget(id: string) {
  return screen.getAllByTestId("widget").find((w) => w.dataset.widgetId === id)!;
}

function titleOf(id: string) {
  return within(widget(id)).getByTestId("widget-title");
}

function setViewport(width: number) {
  act(() => {
    window.innerWidth = width;
    window.dispatchEvent(new Event("resize"));
  });
}

afterEach(() => setViewport(1024));

describe("Board", () => {
  it("renders the status bar and every panel body on the zinc-950 background (was Layout)", async () => {
    await renderApp();
    expect(layout()).toHaveClass("bg-zinc-950");
    for (const id of ["status-bar", "timing", "intelligence", "focus", "chart", "timeline"]) {
      expect(screen.getByTestId(id)).toBeInTheDocument();
    }
  });

  it("places widgets from their cells", () => {
    render(<Harness initial={AB} />);
    expect(widget("B")).toHaveStyle({ position: "absolute", left: "0px", top: `${4 * ROW_STEP}px`, height: `${4 * 44 + 3 * 8}px` });
  });

  it("pointer drag shows a snapped placeholder, then drops and pushes the other widget down", () => {
    let last: BoardModel | null = null;
    render(<Harness initial={AB} onBoard={(b) => (last = b)} />);
    fireEvent.pointerDown(titleOf("B"), { button: 0, clientX: 50, clientY: 300 });
    fireEvent.pointerMove(window, { clientX: 50, clientY: 300 - 2 * ROW_STEP });
    expect(screen.getByTestId("drop-placeholder")).toHaveAttribute("data-cell", "0,2,6,4");
    expect(widget("B")).toHaveAttribute("data-dragging", "true");
    expect(last).toBeNull();
    fireEvent.pointerUp(window, { clientX: 50, clientY: 300 - 2 * ROW_STEP });
    expect(screen.queryByTestId("drop-placeholder")).not.toBeInTheDocument();
    expect(widget("B")).toHaveAttribute("data-cell", "0,2,6,4");
    expect(widget("A")).toHaveAttribute("data-cell", "0,6,6,4");
  });

  it("resizes from the bottom-right corner in whole cells", () => {
    render(<Harness initial={AB} />);
    fireEvent.pointerDown(within(widget("A")).getByTestId("resize-handle"), { button: 0, clientX: 600, clientY: 200 });
    fireEvent.pointerMove(window, { clientX: 600 + 2 * COL_STEP, clientY: 200 + ROW_STEP });
    expect(screen.getByTestId("drop-placeholder")).toHaveAttribute("data-cell", "0,0,8,5");
    fireEvent.pointerUp(window);
    expect(widget("A")).toHaveAttribute("data-cell", "0,0,8,5");
    expect(widget("B")).toHaveAttribute("data-cell", "0,5,6,4");
  });

  it("Escape cancels an active drag", () => {
    render(<Harness initial={AB} />);
    fireEvent.pointerDown(titleOf("B"), { button: 0, clientX: 50, clientY: 300 });
    fireEvent.pointerMove(window, { clientX: 50 + 3 * COL_STEP, clientY: 300 });
    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.pointerUp(window);
    expect(widget("B")).toHaveAttribute("data-cell", "0,4,6,4");
  });

  it("keyboard: arrow keys move the focused widget one cell, Shift+arrow keys resize it", () => {
    render(<Harness initial={AB} />);
    const title = titleOf("B");
    title.focus();
    fireEvent.keyDown(title, { key: "ArrowRight" });
    expect(widget("B")).toHaveAttribute("data-cell", "1,4,6,4");
    fireEvent.keyDown(titleOf("B"), { key: "ArrowRight", shiftKey: true });
    expect(widget("B")).toHaveAttribute("data-cell", "1,4,7,4");
    fireEvent.keyDown(titleOf("B"), { key: "ArrowUp" });
    expect(widget("B")).toHaveAttribute("data-cell", "1,3,7,4");
    expect(widget("A")).toHaveAttribute("data-cell", "0,7,6,4");
  });

  it("keyboard resize respects the timing minimum width", () => {
    const board: BoardModel = { ...AB, widgets: [{ id: "T", type: "timing", x: 0, y: 0, w: 4, h: 6, settings: {} }] };
    render(<Harness initial={board} />);
    fireEvent.keyDown(titleOf("T"), { key: "ArrowLeft", shiftKey: true });
    expect(widget("T")).toHaveAttribute("data-cell", "0,0,4,6");
  });

  it("Narrow screen: at 700 px widgets are one column in row-then-column order and do not drag", () => {
    setViewport(700);
    let changed = false;
    render(<Harness initial={preset("pace")} onBoard={() => (changed = true)} />);
    expect(screen.getByTestId("board")).toHaveAttribute("data-narrow", "true");
    const order = screen.getAllByTestId("widget").map((w) => w.dataset.widgetType);
    expect(order).toEqual(["lapchart", "events", "timing", "driver"]);
    expect(screen.queryByTestId("resize-handle")).not.toBeInTheDocument();
    const title = screen.getAllByTestId("widget-title")[0];
    fireEvent.pointerDown(title, { button: 0, clientX: 10, clientY: 10 });
    fireEvent.pointerMove(window, { clientX: 400, clientY: 400 });
    fireEvent.pointerUp(window);
    fireEvent.keyDown(title, { key: "ArrowDown" });
    expect(changed).toBe(false);
    expect(screen.queryByTestId("drop-placeholder")).not.toBeInTheDocument();
  });

  it("an empty board shows how to add a widget", () => {
    render(<Harness initial={{ ...AB, widgets: [] }} />);
    expect(screen.getByRole("status")).toHaveTextContent(EMPTY_BOARD);
  });

  it("arrow keys on a focused title bar move the widget without stepping the lap", async () => {
    await renderApp();
    const title = titleOf("timeline-1");
    title.focus();
    fireEvent.keyDown(title, { key: "ArrowRight" });
    expect(widget("timeline-1")).toHaveAttribute("data-cell", "5,12,7,2"); // already at the right edge
    fireEvent.keyDown(titleOf("timeline-1"), { key: "ArrowLeft" });
    // The moved widget keeps its cell; the timing list it now overlaps moves below it.
    expect(widget("timeline-1")).toHaveAttribute("data-cell", "4,12,7,2");
    expect(widget("timing-1")).toHaveAttribute("data-cell", "0,14,5,14");
    expect(screen.getByTestId("lap-count")).toHaveTextContent("LAP 1/");
    fireEvent.keyDown(document.body, { key: "ArrowRight" });
    await waitForShown(2);
  });

  it("the classic test board keeps one body per panel", async () => {
    await renderApp();
    expect(screen.getAllByTestId("widget")).toHaveLength(CLASSIC_BOARD.widgets.length);
  });

});

describe("Widget instances on the board", () => {
  function addFromMenu(name: string) {
    fireEvent.click(screen.getByRole("button", { name: "Add widget" }));
    fireEvent.click(screen.getByRole("menuitem", { name }));
  }

  it("+ Widget lists every type and adds a second driver widget below the lowest widget", async () => {
    await renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Add widget" }));
    expect(screen.getAllByRole("menuitem").map((m) => m.textContent)).toEqual([
      "Timing",
      "Events",
      "Driver",
      "Lap times",
      "Timeline",
    ]);
    fireEvent.click(screen.getByRole("menuitem", { name: "Driver" }));
    const drivers = screen.getAllByTestId("widget").filter((w) => w.dataset.widgetType === "driver");
    expect(drivers.map((w) => w.dataset.widgetId)).toEqual(["driver-1", "driver-2"]);
    expect(drivers[1]).toHaveAttribute("data-cell", "0,14,5,8");
    expect(screen.getAllByTestId("focus")).toHaveLength(2);
  });

  it("the remove button deletes a widget and the rest compact upward", async () => {
    await renderApp();
    fireEvent.click(within(widget("events-1")).getByRole("button", { name: "Remove Events widget" }));
    expect(screen.queryByTestId("intelligence")).not.toBeInTheDocument();
    expect(widget("driver-1")).toHaveAttribute("data-cell", "5,0,4,6");
    expect(widget("timeline-1")).toHaveAttribute("data-cell", "5,6,7,2");
  });

  it("A board holds at most 24 widgets: the 25th is refused with a message", async () => {
    fakeBackend();
    const full: BoardModel = {
      ...AB,
      widgets: Array.from({ length: 24 }, (_, i) => ({
        id: `timeline-${i + 1}`,
        type: "timeline" as const,
        x: 0,
        y: i * 2,
        w: 12,
        h: 2,
        settings: {},
      })),
    };
    render(<App initialBoards={boardsWith(full)} />);
    await waitForShown(1);
    addFromMenu("Timing");
    expect(screen.getByTestId("notice")).toHaveTextContent(BOARD_FULL);
    expect(screen.getAllByTestId("widget")).toHaveLength(24);
  });
});
