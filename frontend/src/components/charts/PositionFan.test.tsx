import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PositionsHistoryResponse } from "../../api/types";
import { fanRows, PositionFanView } from "./PositionFan";

function history(analyzed = true): PositionsHistoryResponse {
  return {
    race_id: "r",
    model: "lightgbm",
    analyzed,
    laps: [2.0, 1.8, 1.5].map((expected, i) => ({
      lap: i + 1,
      drivers: [
        { code: "NOR", p_win: 0.4, p_podium: 0.9, expected_position: expected, position_p10: 1, position_p90: 3 },
        { code: "LEC", p_win: 0.1, p_podium: 0.5, expected_position: 3.5, position_p10: 2, position_p90: 6 },
      ],
    })),
  };
}

describe("Position fan widget", () => {
  it("Band follows the history: NOR 2.0, 1.8, 1.5 at laps 1-3 inside a band from 1 to 3", () => {
    expect(fanRows(history(), "NOR")).toEqual([
      { lap: 1, expected: 2.0, band: [1, 3] },
      { lap: 2, expected: 1.8, band: [1, 3] },
      { lap: 3, expected: 1.5, band: [1, 3] },
    ]);
    render(<PositionFanView data={history()} code="NOR" color="#FF8000" lap={3} size={{ width: 400, height: 240 }} />);
    expect(screen.getByTestId("chart-caption")).toHaveTextContent("NOR: expected position");
  });

  it("a band with a missing bound is left out", () => {
    const h = history();
    h.laps[0].drivers[0].position_p90 = null;
    expect(fanRows(h, "NOR")[0].band).toBeNull();
  });

  it("Not analyzed: shows 'Race not analyzed'", () => {
    render(<PositionFanView data={history(false)} code="NOR" color="#fff" lap={3} />);
    expect(screen.getByTestId("chart-message")).toHaveTextContent("Race not analyzed");
  });
});
