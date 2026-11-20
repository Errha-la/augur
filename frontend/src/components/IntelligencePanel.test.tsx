import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { RaceEvent } from "../api/types";
import { raceEvent } from "../test/builders";
import { ABU_DHABI, fakeBackend } from "../test/fakeBackend";
import { IntelligencePanel, NO_EVENTS } from "./IntelligencePanel";

let backend: ReturnType<typeof fakeBackend>;

beforeEach(() => {
  backend = fakeBackend();
});

function panel(events: RaceEvent[], focusCode: string | null = null, focusColor: string | null = null) {
  return <IntelligencePanel raceId={ABU_DHABI} events={events} focusCode={focusCode} focusColor={focusColor} />;
}

function primary() {
  return screen.getByTestId("primary-event");
}

function historyIds() {
  return screen.queryAllByTestId("history-row").map((r) => r.dataset.eventId);
}

describe("Primary event focus", () => {
  it("shows the first event expanded with type, lap, drivers, severity, title, What / Why / Next and evidence", () => {
    render(panel([raceEvent("p", 15, "pace_drop", ["VER", "NOR"], 72.5)]));
    const card = primary();
    expect(card).toHaveTextContent("PACE DROP");
    expect(card).toHaveTextContent("LAP 15");
    expect(card).toHaveTextContent("VER · NOR");
    expect(within(card).getByTestId("severity-bar")).toHaveStyle({ width: "72.5%" });
    expect(within(card).getByRole("heading")).toHaveTextContent("pace_drop VER NOR lap 15");
    expect(card).toHaveTextContent("What of p");
    expect(card).toHaveTextContent("Why of p");
    expect(card).toHaveTextContent("Next of p");
    expect(within(card).getByTestId("evidence")).toHaveTextContent("VER");
  });

  // Scenario: Newer event takes focus
  it("makes a new lap-15 pace_drop primary and moves the previous primary to history", () => {
    const older = raceEvent("old", 12, "position_change", ["LEC"]);
    const { rerender } = render(panel([older]));
    expect(primary()).toHaveAttribute("data-event-id", "old");

    rerender(panel([raceEvent("new", 15, "pace_drop", ["VER"]), older]));
    expect(primary()).toHaveAttribute("data-event-id", "new");
    expect(historyIds()).toEqual(["old"]);
  });

  // Example: two events on one lap
  it("puts the degradation_warning (80) first and the position_change (40) as the first history row", () => {
    // /events order: lap descending, then severity descending.
    render(
      panel([
        raceEvent("deg", 22, "degradation_warning", ["HAM"], 80),
        raceEvent("pos", 22, "position_change", ["RUS"], 40),
        raceEvent("early", 20, "pace_drop", ["ALO"], 90),
      ]),
    );
    expect(primary()).toHaveAttribute("data-event-id", "deg");
    expect(historyIds()[0]).toBe("pos");
  });

  it.each(["degradation_warning", "undercut_window"])(
    "requests the strategy of the first driver at the event lap for %s, showing Simulating... first",
    async (type) => {
      render(panel([raceEvent("s", 12, type, ["NOR", "PIA"])]));
      expect(within(primary()).getByTestId("simulating")).toHaveTextContent("Simulating...");
      const table = await within(primary()).findByTestId("strategy-table");
      expect(table).toHaveTextContent("NOR AT LAP 12");
      expect(backend.of("strategy").map((r) => [r.lap, r.driver])).toEqual([[12, "NOR"]]);
    },
  );

  it("does not request a strategy for other event types", () => {
    render(panel([raceEvent("p", 12, "pace_drop", ["NOR"])]));
    expect(within(primary()).queryByTestId("simulating")).not.toBeInTheDocument();
    expect(backend.of("strategy")).toHaveLength(0);
  });

  it(`shows "${NO_EVENTS}" when there are no events`, () => {
    render(panel([]));
    expect(screen.getByRole("status")).toHaveTextContent(NO_EVENTS);
  });
});

describe("Collapsed event history", () => {
  const events = [
    raceEvent("e10", 10, "pace_drop", ["VER"]),
    raceEvent("e9", 9, "position_change", ["LEC"]),
    raceEvent("e8", 8, "undercut_window", ["NOR", "PIA"]),
  ];

  it("lists every other event collapsed with lap, type and title, in /events order", () => {
    render(panel(events));
    expect(historyIds()).toEqual(["e9", "e8"]);
    const row = screen.getAllByTestId("history-row")[1];
    expect(row).toHaveTextContent("L8");
    expect(row).toHaveTextContent("UNDERCUT");
    expect(row).toHaveTextContent("undercut_window NOR PIA lap 8");
    expect(screen.queryByTestId("history-analysis")).not.toBeInTheDocument();
  });

  // Scenario: Expand a history row
  it("expands the lap 8 row in place without changing the primary card, and collapses it again", () => {
    render(panel(events));
    const row = screen.getAllByTestId("history-row")[1];
    fireEvent.click(within(row).getByRole("button"));
    expect(within(row).getByTestId("history-analysis")).toHaveTextContent("What of e8");
    expect(within(row).getByTestId("history-analysis")).toHaveTextContent("Next of e8");
    expect(primary()).toHaveAttribute("data-event-id", "e10");
    expect(backend.of("strategy")).toHaveLength(0);

    fireEvent.click(within(row).getByRole("button"));
    expect(within(row).queryByTestId("history-analysis")).not.toBeInTheDocument();
  });

  // Scenario: Focus driver events stay in race order
  it("keeps lap order and highlights only the focus driver's lap 8 row", () => {
    render(panel(events, "NOR", "#FF8000"));
    expect(historyIds()).toEqual(["e9", "e8"]);
    const [lap9, lap8] = screen.getAllByTestId("history-row");
    expect(lap8).toHaveAttribute("data-highlight", "true");
    expect(lap9).not.toHaveAttribute("data-highlight");
  });
});
