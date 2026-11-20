import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { driver, raceEvent } from "../test/builders";
import { fixtures, type RequestCtx } from "../test/fakeBackend";
import { goToLap, renderApp } from "../test/renderApp";

const MCLAREN = "#FF8000";
const undercut = raceEvent("u", 8, "undercut_window", ["NOR", "PIA"], 70);
const later = raceEvent("p", 9, "pace_drop", ["VER"], 50);

function state({ raceId, lap }: RequestCtx) {
  return {
    ...fixtures.state,
    race_id: raceId,
    lap,
    drivers: [
      driver("NOR", 1, { team: "McLaren", team_color: MCLAREN }),
      driver("PIA", 2, { team: "McLaren", team_color: MCLAREN }),
      driver("VER", 3, { team: "Red Bull Racing", team_color: "#3671C6" }),
    ],
  };
}

function events({ raceId, lap }: RequestCtx) {
  return { race_id: raceId, lap, model: "m", analyzed: true, events: [later, undercut].filter((e) => e.lap <= lap) };
}

function hasColour(el: HTMLElement) {
  // jsdom normalises #FF8000 to rgb(255, 128, 0) in style attributes.
  return /rgb\(255, 128, 0\)|#ff8000/i.test(el.getAttribute("style") ?? "");
}

describe("Focus driver highlights — Highlighted event", () => {
  it("highlights NOR's undercut_window card, history row and timeline marker in NOR's team colour", async () => {
    await renderApp({ handlers: { state, events } });

    const row = screen.getByTestId("row-NOR");
    expect(row).toHaveAttribute("data-focus", "true");
    expect(hasColour(row)).toBe(true);
    expect(screen.getByTestId("row-VER")).not.toHaveAttribute("data-focus");

    // Lap 8: the undercut is the primary card.
    await goToLap(8);
    const card = screen.getByTestId("primary-event");
    expect(card).toHaveAttribute("data-event-id", "u");
    expect(card).toHaveAttribute("data-highlight", "true");
    expect(hasColour(card)).toBe(true);
    const marker8 = screen.getAllByTestId("timeline-marker").find((m) => m.dataset.lap === "8")!;
    expect(marker8).toHaveAttribute("data-highlight", "true");
    expect(hasColour(marker8)).toBe(true);

    // Lap 9: a newer VER event is primary, the undercut is in history.
    await goToLap(9);
    const primary = screen.getByTestId("primary-event");
    expect(primary).toHaveAttribute("data-event-id", "p");
    expect(primary).not.toHaveAttribute("data-highlight");
    const historyRow = screen.getAllByTestId("history-row").find((r) => r.dataset.eventId === "u")!;
    expect(historyRow).toHaveAttribute("data-highlight", "true");
    expect(hasColour(historyRow)).toBe(true);

    const markers = screen.getAllByTestId("timeline-marker");
    expect(markers.find((m) => m.dataset.lap === "8")).toHaveAttribute("data-highlight", "true");
    expect(markers.find((m) => m.dataset.lap === "9")).not.toHaveAttribute("data-highlight");
  });
});
