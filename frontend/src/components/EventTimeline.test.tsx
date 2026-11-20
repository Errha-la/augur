import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { raceEvent } from "../test/builders";
import type { RequestCtx } from "../test/fakeBackend";
import { advance, goToLap, lapCount, renderApp, waitForShown } from "../test/renderApp";
import { EventTimeline } from "./EventTimeline";

const allEvents = [
  raceEvent("e38", 38, "pace_drop", ["VER"]),
  raceEvent("e30", 30, "degradation_warning", ["HAM"]),
  raceEvent("e12", 12, "undercut_window", ["NOR", "PIA"]),
  raceEvent("e5", 5, "position_change", ["LEC"]),
];

function events({ raceId, lap }: RequestCtx) {
  return { race_id: raceId, lap, model: "m", analyzed: true, events: allEvents.filter((e) => e.lap <= lap) };
}

function markerLaps() {
  return screen.getAllByTestId("timeline-marker").map((m) => Number(m.dataset.lap));
}

describe("Event timeline navigation", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  it("marks each event up to the current lap, positioned by lap and coloured by type", () => {
    render(
      <EventTimeline lap={30} totalLaps={58} events={allEvents.filter((e) => e.lap <= 30)} focusCode={null} focusColor={null} onJump={() => {}} />,
    );
    expect(markerLaps().sort((a, b) => a - b)).toEqual([5, 12, 30]);
    const lap30 = screen.getAllByTestId("timeline-marker").find((m) => m.dataset.lap === "30")!;
    expect(lap30).toHaveStyle({ left: `${(29 / 57) * 100}%`, backgroundColor: "#fbcc1c" });
    const lap5 = screen.getAllByTestId("timeline-marker").find((m) => m.dataset.lap === "5")!;
    expect(lap5).toHaveStyle({ backgroundColor: "#38bdf8" });
  });

  // Scenario: Jump to an event
  it("jumps from lap 40 to lap 12, stops playback, and shows only markers up to lap 12", async () => {
    await renderApp({ handlers: { events } });
    await goToLap(40);
    expect(markerLaps().sort((a, b) => a - b)).toEqual([5, 12, 30, 38]);
    fireEvent.click(screen.getByRole("button", { name: "Play" }));

    const timeline = screen.getByTestId("event-timeline");
    const marker = within(timeline).getAllByTestId("timeline-marker").find((m) => m.dataset.lap === "12")!;
    fireEvent.click(marker);

    await waitForShown(12);
    expect(lapCount()).toBe("LAP 12/58");
    expect(screen.getByRole("button", { name: "Play" })).toBeInTheDocument();
    expect(markerLaps().sort((a, b) => a - b)).toEqual([5, 12]);
    await advance(2000);
    expect(lapCount()).toBe("LAP 12/58");
  });
});
