import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PositionDistributionResponse } from "../../api/types";
import { HeatmapView } from "./Heatmap";

function dist(drivers: PositionDistributionResponse["drivers"], analyzed = true): PositionDistributionResponse {
  return { race_id: "r", lap: 20, model: "lightgbm", analyzed, drivers };
}

const colors = { NOR: "#FF8000", LEC: "#E8002D" };

describe("Position heatmap widget", () => {
  it("Cell labels: [0.61, 0.22, 0.1, 0.07] reads 61%, 22%, 10% and an empty P4; every cell has a hover text", () => {
    render(<HeatmapView data={dist([{ code: "NOR", position_distribution: [0.61, 0.22, 0.1, 0.07] }])} teamColors={colors} />);
    const cells = within(screen.getByTestId("odds-NOR")).getAllByTestId("odds-cell");
    expect(cells.map((c) => c.textContent)).toEqual(["61%", "22%", "10%", ""]);
    expect(cells[3]).toHaveAttribute("title", "NOR P4: 7%");
  });

  it("rows follow the response order; a null row keeps its code and empty cells", () => {
    render(
      <HeatmapView
        data={dist([
          { code: "LEC", position_distribution: [0.5, 0.5] },
          { code: "NOR", position_distribution: null },
        ])}
        teamColors={colors}
      />,
    );
    expect(screen.getAllByTestId(/^odds-[A-Z]/).map((r) => r.dataset.testid)).toEqual(["odds-LEC", "odds-NOR"]);
    const nor = screen.getByTestId("odds-NOR");
    expect(nor).toHaveTextContent("NOR");
    expect(within(nor).getAllByTestId("odds-cell").every((c) => c.textContent === "")).toBe(true);
  });

  it("Stored before the distribution existed: every distribution null", () => {
    render(<HeatmapView data={dist([{ code: "NOR", position_distribution: null }])} teamColors={colors} />);
    expect(screen.getByTestId("chart-message")).toHaveTextContent("No distribution stored; re-run analyze");
  });

  it("not analyzed", () => {
    render(<HeatmapView data={dist([], false)} teamColors={colors} />);
    expect(screen.getByTestId("chart-message")).toHaveTextContent("Race not analyzed");
  });
});
