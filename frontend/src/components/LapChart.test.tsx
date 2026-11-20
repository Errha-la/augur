import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DriverState, LapRow } from "../api/types";
import { chartModel } from "../lib/chartModel";
import { driver, lapRow } from "../test/builders";
import { LapChart } from "./LapChart";

function grid(count: number, focus?: { team?: string }): DriverState[] {
  return Array.from({ length: count }, (_, i) =>
    driver(`D${String(i + 1).padStart(2, "0")}`, i + 1, { team: `Team ${i}`, team_color: `#${String(i).padStart(6, "0")}`, ...focus }),
  );
}

function lapsFor(codes: string[], upTo: number): LapRow[] {
  return codes.flatMap((c) => Array.from({ length: upTo }, (_, i) => lapRow(c, i + 1, 90 + i / 10)));
}

function codesOf(drivers: DriverState[], focus: string, lap = 10) {
  return chartModel(drivers, [], focus, lap).series.map((s) => s.code);
}

describe("Lap-time chart — neighbours", () => {
  const drivers = grid(20);

  it.each([
    ["1", "D01", ["D01", "D02"]],
    ["5", "D05", ["D04", "D05", "D06"]],
    ["last (20)", "D20", ["D19", "D20"]],
  ])("focus at P%s plots %s and its neighbours", (_, focus, expected) => {
    expect(codesOf(drivers, focus)).toEqual(expected);
  });

  it("draws the focus line 3 px at full opacity and neighbours 1.5 px at 75%", () => {
    const series = chartModel(drivers, [], "D05", 10).series;
    expect(series.map((s) => [s.code, s.strokeWidth, s.opacity, s.dots])).toEqual([
      ["D04", 1.5, 0.75, false],
      ["D05", 3, 1, false],
      ["D06", 1.5, 0.75, false],
    ]);
  });
});

describe("Lap-time chart — Teammate neighbour", () => {
  const mercedes = "#27F4D2";
  const drivers = [
    driver("VER", 1, { team: "Red Bull Racing", team_color: "#3671C6" }),
    driver("NOR", 2, { team: "McLaren", team_color: "#FF8000" }),
    driver("LEC", 3, { team: "Ferrari", team_color: "#E8002D" }),
    driver("HAM", 4, { team: "Mercedes", team_color: mercedes }),
    driver("RUS", 5, { team: "Mercedes", team_color: mercedes }),
  ];

  it("gives RUS dots and the thin line, HAM the thick line without dots, both in Mercedes colour", () => {
    const series = chartModel(drivers, [], "HAM", 10).series;
    const ham = series.find((s) => s.code === "HAM")!;
    const rus = series.find((s) => s.code === "RUS")!;
    expect([ham.color, rus.color]).toEqual([mercedes, mercedes]);
    expect([ham.strokeWidth, ham.opacity, ham.dots]).toEqual([3, 1, false]);
    expect([rus.strokeWidth, rus.opacity, rus.dots]).toEqual([1.5, 0.75, true]);
  });

  it("lists HAM and RUS by code in the legend", () => {
    render(<LapChart lap={10} drivers={drivers} laps={lapsFor(["LEC", "HAM", "RUS"], 10)} focusCode="HAM" size={{ width: 600, height: 300 }} />);
    expect(screen.getByTestId("legend-HAM")).toHaveTextContent("HAM");
    expect(screen.getByTestId("legend-HAM")).toHaveAttribute("data-role", "focus");
    expect(screen.getByTestId("legend-RUS")).toHaveTextContent("RUS");
    expect(screen.getByTestId("legend-LEC")).toBeInTheDocument();
  });
});

describe("Lap-time chart — Neighbours follow the current lap", () => {
  const at = (lap: number) => [
    driver("VER", 1),
    driver("NOR", 2),
    driver("LEC", 3),
    driver("PIA", 4),
    driver("HAM", 5),
    driver(lap === 30 ? "ALO" : "GAS", 6),
    driver(lap === 30 ? "GAS" : "ALO", 7),
  ];
  const laps = lapsFor(["PIA", "HAM", "ALO", "GAS"], 31);

  it("plots ALO for laps 1-30 at lap 30 and GAS for laps 1-31 at lap 31", () => {
    const m30 = chartModel(at(30), laps.filter((r) => r.lap <= 30), "HAM", 30);
    expect(m30.series.map((s) => s.code)).toEqual(["PIA", "HAM", "ALO"]);
    expect(m30.rows.map((r) => r.lap)).toEqual(Array.from({ length: 30 }, (_, i) => i + 1));
    expect(m30.rows.every((r) => r.ALO != null)).toBe(true);

    const m31 = chartModel(at(31), laps, "HAM", 31);
    expect(m31.series.map((s) => s.code)).toEqual(["PIA", "HAM", "GAS"]);
    expect(m31.rows).toHaveLength(31);
    expect(m31.rows.every((r) => r.GAS != null)).toBe(true);
  });

  it("titles the legend with the current lap", () => {
    const { rerender } = render(<LapChart lap={30} drivers={at(30)} laps={laps} focusCode="HAM" size={{ width: 600, height: 300 }} />);
    expect(screen.getByTestId("chart-legend")).toHaveTextContent("Neighbours at lap 30");
    expect(screen.getByTestId("legend-ALO")).toBeInTheDocument();
    rerender(<LapChart lap={31} drivers={at(31)} laps={laps} focusCode="HAM" size={{ width: 600, height: 300 }} />);
    expect(screen.getByTestId("chart-legend")).toHaveTextContent("Neighbours at lap 31");
    expect(screen.getByTestId("legend-GAS")).toBeInTheDocument();
    expect(screen.queryByTestId("legend-ALO")).not.toBeInTheDocument();
  });
});

describe("Lap-time chart — Chart stops at the current lap", () => {
  it("plots no lap above 20 for any driver, even if later rows are passed in", () => {
    const drivers = grid(3);
    const laps = lapsFor(["D01", "D02", "D03"], 25);
    const model = chartModel(drivers, laps, "D02", 20);
    expect(model.rows.at(-1)?.lap).toBe(20);
    expect(Math.max(...model.rows.map((r) => r.lap as number))).toBe(20);
    for (const s of model.series) expect(model.rows.at(-1)?.[s.code]).not.toBeNull();
  });

  it("leaves null lap times as gaps", () => {
    const laps = [lapRow("D01", 1, 91), lapRow("D01", 2, null), lapRow("D01", 3, 90)];
    const model = chartModel(grid(2), laps, "D01", 3);
    expect(model.rows.map((r) => r.D01)).toEqual([91, null, 90]);
  });

  it("renders one SVG line per plotted driver with the focus line 3 px", () => {
    const drivers = grid(5);
    const { container } = render(
      <LapChart lap={20} drivers={drivers} laps={lapsFor(["D02", "D03", "D04"], 20)} focusCode="D03" size={{ width: 600, height: 300 }} />,
    );
    const curves = [...container.querySelectorAll("path.recharts-line-curve")];
    expect(curves).toHaveLength(3);
    expect(curves.map((c) => c.getAttribute("stroke-width")).sort()).toEqual(["1.5", "1.5", "3"]);
  });
});
