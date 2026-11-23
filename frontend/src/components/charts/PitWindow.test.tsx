import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PitPlan, PitWindowResponse } from "../../api/types";
import { emptyWindowText, pitWindowModel, PitWindowView } from "./PitWindow";

function plan(pit_lap: number | null, mean: number, best: number): PitPlan {
  return { pit_lap, mean_s: mean, p10_s: mean - 10, p90_s: mean + 12, delta_s: Math.round((mean - best) * 1000) / 1000 };
}

function window(lap: number, plans: PitPlan[], best: number | null): PitWindowResponse {
  return { race_id: "r", lap, driver: "NOR", runs: 1000, seed: 42, pit_loss_s: 22.6, best_pit_lap: best, plans };
}

describe("Pit window widget", () => {
  it("Best lap and no-stop line: laps 21 to 56 plus a no-stop plan, best lap 32", () => {
    const best = 3375;
    const plans = Array.from({ length: 36 }, (_, i) => plan(21 + i, best + Math.abs(21 + i - 32) * 0.5, best));
    plans.push(plan(null, best + 8, best));
    const data = window(20, plans, 32);
    render(<PitWindowView data={data} totalLaps={58} color="#FF8000" size={{ width: 500, height: 300 }} />);
    expect(screen.getByTestId("best-pit-lap")).toHaveTextContent("Best: lap 32");
    expect(screen.getByTestId("no-stop")).toHaveTextContent("No further stop");
    expect(screen.getByText("Green race assumed")).toBeInTheDocument();

    const model = pitWindowModel(data);
    expect(model.rows.map((r) => r.pit_lap)).toEqual(Array.from({ length: 36 }, (_, i) => 21 + i));
    expect(model.noStopDelta).toBe(8);
    // The band is on the delta scale: p10/p90 minus the best plan's mean.
    expect(model.rows.find((r) => r.pit_lap === 32)).toEqual({ pit_lap: 32, delta_s: 0, band: [-10, 12] });
  });

  it("no no-stop plan: no dashed line", () => {
    render(<PitWindowView data={window(15, [plan(16, 100, 100)], 16)} totalLaps={58} color="#fff" />);
    expect(screen.queryByTestId("no-stop")).not.toBeInTheDocument();
  });

  it.each([
    [2, "Not enough laps yet"],
    [56, "No pit window left"],
    [58, "No pit window left"],
  ])("Empty window messages: lap %s of 58 reads '%s'", (lap, text) => {
    expect(emptyWindowText(lap, 58)).toBe(text);
    render(<PitWindowView data={window(lap, [], null)} totalLaps={58} color="#fff" />);
    expect(screen.getByTestId("chart-message")).toHaveTextContent(text);
  });
});
