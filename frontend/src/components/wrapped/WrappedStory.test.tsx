import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { wrappedResponse } from "../../test/builders";
import { NO_CALLS, NO_EVENTS, NO_SKILL } from "./cards";
import { WrappedStory } from "./WrappedStory";

const COLORS = { VER: "#3671C6", NOR: "#FF8000" };

function story(data = wrappedResponse(), onClose = vi.fn()) {
  render(<WrappedStory data={data} onClose={onClose} teamColors={COLORS} />);
  return onClose;
}

function card() {
  return screen.getByTestId("wrapped-card");
}

function goTo(n: number) {
  for (let i = 1; i < n; i++) fireEvent.keyDown(window, { key: "ArrowRight" });
}

describe("Story card sequence", () => {
  it("shows 7 cards in order with 7 progress segments", () => {
    story();
    expect(screen.getAllByTestId("progress-segment")).toHaveLength(7);
    const slugs = [];
    for (let i = 0; i < 7; i++) {
      slugs.push(card().dataset.card);
      fireEvent.keyDown(window, { key: "ArrowRight" });
    }
    expect(slugs).toEqual(["summary", "podium-call", "accuracy", "best-call", "biggest-miss", "biggest-moment", "driver"]);
  });

  // Example: key presses
  it.each([
    [1, "ArrowLeft", 1],
    [1, "ArrowRight", 2],
    [7, "ArrowRight", 7],
  ])("card %i, %s → card %i", (from, key, to) => {
    const onClose = story();
    goTo(from);
    expect(card().dataset.index).toBe(String(from));
    fireEvent.keyDown(window, { key });
    expect(card().dataset.index).toBe(String(to));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("any card, Esc → overlay closes", () => {
    const onClose = story();
    goTo(4);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clicking the right half goes forward and the left half goes back", () => {
    story();
    const stage = screen.getByTestId("story-stage");
    stage.getBoundingClientRect = () => ({ left: 100, top: 0, width: 400, height: 700, right: 500, bottom: 700, x: 100, y: 0, toJSON() {} });
    fireEvent.click(stage, { clientX: 450 });
    expect(card().dataset.index).toBe("2");
    fireEvent.click(stage, { clientX: 150 });
    expect(card().dataset.index).toBe("1");
    fireEvent.click(stage, { clientX: 150 });
    expect(card().dataset.index).toBe("1");
  });

  it("uses each card's accent and the footer with model, author and race", () => {
    story();
    const accents = [];
    for (let i = 0; i < 7; i++) {
      accents.push(card().dataset.accent);
      expect(within(card()).getByTestId("card-footer")).toHaveTextContent(
        "AUGUR · lightgbm by AUGUR · Abu Dhabi Grand Prix 2024",
      );
      fireEvent.keyDown(window, { key: "ArrowRight" });
    }
    // Summary = winner VER's colour; Accuracy red because the skill is negative; Driver = NOR's team colour.
    expect(accents).toEqual(["#3671C6", "#fbcc1c", "#f12f32", "#c084fc", "#f12f32", "#d4d4d8", "#FF8000"]);
  });
});

describe("Story cards content", () => {
  // Scenario: Accuracy card
  it("Accuracy: -3.2 skill reads 3.2% worse with the red accent, lap times beat by 12.5%", () => {
    story();
    goTo(3);
    expect(card().dataset.accent).toBe("#f12f32");
    expect(screen.getByTestId("accuracy-skill")).toHaveTextContent("Podium calls: 3.2% worse than current order");
    expect(screen.getByTestId("accuracy-laps")).toHaveTextContent("Lap times: beat baseline by 12.5%");
    expect(screen.getByTestId("accuracy-hits")).toHaveTextContent("Event calls: 50% right (1/2)");
  });

  it("Accuracy: a positive skill uses the emerald accent", () => {
    story(wrappedResponse({ score: { ...wrappedResponse().score, position_skill_pct: 12.0 } }));
    goTo(3);
    expect(card().dataset.accent).toBe("#34d399");
    expect(screen.getByTestId("accuracy-skill")).toHaveTextContent("Podium calls: 12.0% better than current order");
  });

  // Scenario: Podium Call card
  it("Podium Call: reads the sentence and shows each predicted driver's podium probability", () => {
    story();
    goTo(2);
    expect(screen.getByTestId("podium-call-text")).toHaveTextContent(
      "At lap 29 AUGUR's podium was VER, NOR, LEC — 2 of 3 correct",
    );
    const rows = screen.getAllByTestId("podium-call-driver");
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringContaining("VER92%"),
      expect.stringContaining("NOR71%"),
      expect.stringContaining("LEC55%"),
    ]);
  });

  it("event cards show lap, drivers, title, what AUGUR said and the outcome", () => {
    story();
    goTo(4);
    const c = card();
    expect(c).toHaveTextContent("LAP 18");
    expect(c).toHaveTextContent("NOR · PIA");
    expect(c).toHaveTextContent("What of best");
    expect(within(c).getByTestId("card-outcome")).toHaveTextContent("hit");
    expect(within(c).getByTestId("card-outcome")).toHaveTextContent("NOR was ahead of PIA on lap 26");
  });

  it("empty states for null highlights and a null skill", () => {
    story(
      wrappedResponse({
        best_call: null,
        biggest_miss: null,
        biggest_moment: null,
        score: { ...wrappedResponse().score, position_skill_pct: null },
      }),
    );
    goTo(3);
    expect(screen.getByTestId("accuracy-skill")).toHaveTextContent(NO_SKILL);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(within(card()).getByTestId("card-empty")).toHaveTextContent(NO_CALLS);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(within(card()).getByTestId("card-empty")).toHaveTextContent(NO_CALLS);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(within(card()).getByTestId("card-empty")).toHaveTextContent(NO_EVENTS);
  });

  it("Driver card shows grid to final position, lines, stints and events", () => {
    story();
    goTo(7);
    expect(screen.getByTestId("driver-positions")).toHaveTextContent("P1 → P2");
    expect(screen.getByRole("img", { name: "Position by lap" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Podium chance by lap" })).toBeInTheDocument();
    expect(screen.getByTestId("driver-stints").children).toHaveLength(2);
    expect(card()).toHaveTextContent("UNDERCUT");
  });

  it("Driver card falls back to the lap 1 position when the grid is unknown, and draws P1 at the top", () => {
    const flatP1 = Array.from({ length: 58 }, (_, i) => ({ lap: i + 1, position: 1 }));
    story(wrappedResponse({}, { grid_position: null, final_position: 1, positions_by_lap: flatP1, events: [] }));
    goTo(7);
    const positions = screen.getByTestId("driver-positions");
    expect(positions).toHaveTextContent("P1 → P1");
    expect(positions).toHaveTextContent("Lap 1 P1 → Finish P1");
    expect(positions).not.toHaveTextContent("?");
    const line = screen.getByRole("img", { name: "Position by lap" }).querySelector("polyline")!;
    const ys = line.getAttribute("points")!.split(" ").map((p) => Number(p.split(",")[1]));
    expect(Math.max(...ys)).toBe(0); // P1 every lap → the top edge
    expect(card()).toHaveTextContent("No events for NOR this race");
  });

  it("keeps the card node at 1080×1920 while the stage is scaled", () => {
    story();
    expect(card()).toHaveStyle({ width: "1080px", height: "1920px" });
  });
});
