import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { StintsResponse } from "../../api/types";
import { segments, StintsView } from "./Stints";

function stints(): StintsResponse {
  return {
    race_id: "r",
    lap: 30,
    drivers: [
      {
        code: "NOR",
        stints: [
          { stint: 1, compound: "MEDIUM", start_lap: 1, end_lap: 25, start_tyre_age: 1 },
          { stint: 2, compound: "HARD", start_lap: 26, end_lap: 30, start_tyre_age: 1 },
        ],
      },
      { code: "LEC", stints: [{ stint: 1, compound: "SOFT", start_lap: 1, end_lap: 3, start_tyre_age: 2 }] },
    ],
  };
}

describe("Tyre stints widget", () => {
  it("Running stint ends at the current lap: MEDIUM 1-25 and HARD 26-30, laps 31 onwards empty", () => {
    render(<StintsView data={stints()} totalLaps={58} focusCode="NOR" />);
    const row = screen.getByTestId("stints-NOR");
    const segs = within(row).getAllByTestId("stint-segment");
    expect(segs.map((s) => [s.dataset.compound, s.dataset.laps])).toEqual([
      ["MEDIUM", "1-25"],
      ["HARD", "26-30"],
    ]);
    const [, hard] = segments(stints().drivers[0].stints, 58);
    // The HARD segment ends at lap 30 of 58: nothing is drawn after it.
    expect(hard.left + hard.width).toBeCloseTo((30 / 58) * 100);
    expect(row).toHaveAttribute("data-focus", "true");
    expect(screen.getByTestId("stints-LEC")).not.toHaveAttribute("data-focus");
  });

  it("writes the compound letter only in segments of at least 4 laps", () => {
    render(<StintsView data={stints()} totalLaps={58} focusCode={null} />);
    expect(within(screen.getByTestId("stints-NOR")).getAllByTestId("stint-segment").map((s) => s.textContent)).toEqual([
      "M",
      "H",
    ]);
    expect(within(screen.getByTestId("stints-LEC")).getByTestId("stint-segment")).toHaveTextContent("");
  });

  it("rows follow the response order", () => {
    render(<StintsView data={stints()} totalLaps={58} focusCode={null} />);
    expect(screen.getAllByTestId(/^stints-/).map((r) => r.dataset.testid)).toEqual(["stints-NOR", "stints-LEC"]);
  });

  it("shows 'No laps yet' when no driver has a stint", () => {
    render(<StintsView data={{ race_id: "r", lap: 1, drivers: [{ code: "NOR", stints: [] }] }} totalLaps={58} focusCode={null} />);
    expect(screen.getByTestId("chart-message")).toHaveTextContent("No laps yet");
  });
});
