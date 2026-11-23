import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";
import type { Board, WidgetInstance } from "../canvas/board";
import { raceEvent } from "../test/builders";
import { fakeBackend, type RequestCtx } from "../test/fakeBackend";
import { boardsWith, goToLap, waitForShown } from "../test/renderApp";

type WidgetSpec = Omit<WidgetInstance, "settings"> & { settings?: WidgetInstance["settings"] };

function boardOf(widgets: WidgetSpec[]): Board {
  return { id: "t", name: "Test", presetId: null, widgets: widgets.map((w) => ({ settings: {}, ...w })) };
}

async function show(board: Board) {
  const backend = fakeBackend();
  render(<App initialBoards={boardsWith(board)} />);
  await waitForShown(1);
  return backend;
}

function widget(id: string) {
  return screen.getAllByTestId("widget").find((w) => w.dataset.widgetId === id)!;
}

function focusLegend(id: string) {
  return within(widget(id))
    .getAllByTestId(/^legend-/)
    .find((l) => l.dataset.role === "focus")!;
}

describe("Per-widget driver", () => {
  it("Two pinned lap charts: each plots its own driver while the NOR row is highlighted", async () => {
    await show(
      boardOf([
        { id: "timing-1", type: "timing", x: 0, y: 0, w: 4, h: 10 },
        { id: "lapchart-1", type: "lapchart", x: 4, y: 0, w: 4, h: 5, settings: { driver: "LEC" } },
        { id: "lapchart-2", type: "lapchart", x: 8, y: 0, w: 4, h: 5, settings: { driver: "PIA" } },
      ]),
    );
    fireEvent.click(screen.getByTestId("row-SAI"));
    fireEvent.click(screen.getByTestId("row-NOR"));
    expect(screen.getByTestId("row-NOR")).toHaveAttribute("data-focus", "true");
    expect(focusLegend("lapchart-1")).toHaveTextContent("LEC");
    expect(focusLegend("lapchart-2")).toHaveTextContent("PIA");
    // Neighbours of LEC (P4) are RUS (P3) and VER (P5).
    expect(within(widget("lapchart-1")).getByTestId("legend-RUS")).toHaveAttribute("data-role", "ahead");
    expect(within(widget("lapchart-1")).getByTestId("legend-VER")).toHaveAttribute("data-role", "behind");
    expect(within(widget("lapchart-1")).getByTestId("widget-title")).toHaveTextContent("LEC");
  });

  it("the title-bar picker lists Follow focus and every driver, and pins one widget only", async () => {
    await show(
      boardOf([
        { id: "lapchart-1", type: "lapchart", x: 0, y: 0, w: 6, h: 5 },
        { id: "lapchart-2", type: "lapchart", x: 6, y: 0, w: 6, h: 5 },
      ]),
    );
    const picker = within(widget("lapchart-2")).getByRole("combobox", { name: "Driver for Lap times widget" });
    const options = within(picker).getAllByRole("option").map((o) => o.textContent);
    expect(options[0]).toBe("Follow focus (NOR)");
    expect(options).toHaveLength(21);
    fireEvent.change(picker, { target: { value: "PIA" } });
    expect(focusLegend("lapchart-2")).toHaveTextContent("PIA");
    expect(focusLegend("lapchart-1")).toHaveTextContent("NOR");
    fireEvent.change(picker, { target: { value: "" } });
    expect(focusLegend("lapchart-2")).toHaveTextContent("NOR");
  });

  it("Pinned driver missing: a driver widget pinned to SAR shows the message and the focus driver's panel", async () => {
    await show(
      boardOf([
        { id: "timing-1", type: "timing", x: 0, y: 0, w: 5, h: 10 },
        { id: "driver-1", type: "driver", x: 5, y: 0, w: 7, h: 8, settings: { driver: "SAR" } },
      ]),
    );
    fireEvent.click(screen.getByTestId("row-VER"));
    const w = widget("driver-1");
    expect(within(w).getByTestId("driver-missing")).toHaveTextContent("SAR is not in this race");
    expect(within(w).getByTestId("focus-panel")).toHaveTextContent("VER");
    expect(within(w).getByRole("combobox")).toHaveValue("SAR");
  });

  it("Shared request: two driver widgets following NOR, paused at lap 20, send one /strategy request", async () => {
    const backend = await show(
      boardOf([
        { id: "driver-1", type: "driver", x: 0, y: 0, w: 6, h: 8 },
        { id: "driver-2", type: "driver", x: 6, y: 0, w: 6, h: 8 },
      ]),
    );
    await goToLap(20);
    await waitFor(() => expect(screen.getAllByTestId("strategy-table")).toHaveLength(2));
    const calls = backend.of("strategy").filter((r) => r.lap === 20 && r.driver === "NOR");
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain("/strategy?lap=20&driver=NOR");
    expect(backend.of("positions/history").filter((r) => r.lap === 20)).toHaveLength(1);
  });
});

describe("Event type filter", () => {
  const deg = raceEvent("d", 22, "degradation_warning", ["VER"], 80);
  const pos = raceEvent("p", 22, "position_change", ["NOR", "PIA"], 40);
  const events = ({ raceId, lap }: RequestCtx) => ({
    race_id: raceId,
    lap,
    model: "m",
    analyzed: true,
    commentary_model: null,
    events: [deg, pos].filter((e) => e.lap <= lap),
  });

  async function showEvents(types?: string[]) {
    fakeBackend({ handlers: { events } });
    render(<App initialBoards={boardsWith(boardOf([{ id: "events-1", type: "events", x: 0, y: 0, w: 12, h: 8, settings: { types } }]))} />);
    await waitForShown(1);
  }

  it("Filtered primary event: an events widget showing only position_change picks it at lap 22", async () => {
    await showEvents(["position_change"]);
    await goToLap(22);
    expect(screen.getByTestId("primary-event")).toHaveAttribute("data-event-id", "p");
    expect(screen.queryByTestId("history-row")).not.toBeInTheDocument();
  });

  it("chips toggle the shown types, and no match shows the message", async () => {
    await showEvents();
    expect(within(screen.getByTestId("intelligence")).getByRole("status")).toHaveTextContent("No significant events yet");
    await goToLap(22);
    expect(screen.getByTestId("primary-event")).toHaveAttribute("data-event-id", "d");
    const chips = within(screen.getByRole("group", { name: "Event types shown" }));
    const degChip = chips.getByRole("button", { name: "DEGRADATION" });
    expect(degChip).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(degChip);
    expect(degChip).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("primary-event")).toHaveAttribute("data-event-id", "p");
    fireEvent.click(chips.getByRole("button", { name: "POSITION" }));
    expect(within(screen.getByTestId("intelligence")).getByRole("status")).toHaveTextContent("No matching events yet");
  });
});
