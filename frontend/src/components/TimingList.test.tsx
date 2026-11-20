import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DriverPositions, DriverPrediction, DriverState, LapRow } from "../api/types";
import { driver, lapRow, positions, prediction } from "../test/builders";
import { TimingList } from "./TimingList";

function renderList(opts: {
  drivers: DriverState[];
  laps?: LapRow[];
  predictions?: DriverPrediction[];
  positions?: DriverPositions[];
  lap?: number;
  onFocus?: (code: string) => void;
}) {
  render(
    <TimingList
      lap={opts.lap ?? 10}
      drivers={opts.drivers}
      laps={opts.laps ?? []}
      predictions={opts.predictions ?? []}
      positions={opts.positions ?? []}
      focusCode={null}
      onFocus={opts.onFocus ?? (() => {})}
    />,
  );
}

function field(code: string, name: string) {
  return within(screen.getByTestId(`row-${code}`)).getByText(
    (_, el) => el?.getAttribute("data-field") === name,
  );
}

describe("Timing list — formatted fields", () => {
  const drivers = [
    driver("VER", 1, { gap_to_leader_s: 0 }),
    driver("NOR", 2, { gap_to_leader_s: 2.5, last_lap_time_s: 96.512, compound: "MEDIUM", tyre_age_laps: 7 }),
    driver("LEC", 3),
    driver("SAR", 20, { gap_to_leader_s: null, laps_behind_leader: 1 }),
  ];
  const preds = [prediction("NOR", { deg_s_per_lap: 0.082, predicted_next_lap_s: null })];
  const pos = [positions("NOR", { p_podium: 0.418, p_win: 0.003 })];

  it.each([
    ["position 3", "LEC", "position", "03"],
    ["gap, leader", "VER", "gap", "LEADER"],
    ["gap 2.5", "NOR", "gap", "+2.500"],
    ["gap, lapped", "SAR", "gap", "+1 LAP"],
    ["last lap 96.512", "NOR", "last", "1:36.512"],
    ["degradation 0.082", "NOR", "deg", "+0.082/lap"],
    ["podium 0.418", "NOR", "podium", "42%"],
    ["win 0.003", "NOR", "win", "<1%"],
  ])("%s", (_, code, name, text) => {
    renderList({ drivers, predictions: preds, positions: pos });
    expect(field(code, name)).toHaveTextContent(text);
  });

  it("compound MEDIUM, tyre age 7 → M in #fbcc1c, then 7", () => {
    renderList({ drivers, predictions: preds, positions: pos });
    const compound = field("NOR", "compound");
    expect(compound).toHaveTextContent("M");
    expect(compound).toHaveStyle({ color: "#fbcc1c" });
    expect(field("NOR", "tyre-age")).toHaveTextContent("7");
  });

  it("predicted next lap null → dash", () => {
    renderList({ drivers, predictions: preds, positions: pos });
    expect(within(field("NOR", "next")).getByTestId("dash")).toBeInTheDocument();
  });

  it("orders rows by position and shows the CLIFF tag", () => {
    renderList({
      drivers: [driver("B", 2), driver("A", 1), driver("C", 3)],
      predictions: [prediction("C", { cliff: true })],
    });
    const rows = screen.getAllByTestId(/^row-/).map((r) => r.dataset.testid);
    expect(rows).toEqual(["row-A", "row-B", "row-C"]);
    expect(field("C", "deg")).toHaveTextContent("CLIFF");
    expect(field("B", "deg")).not.toHaveTextContent("CLIFF");
  });

  it("draws the podium bar proportional to the podium probability", () => {
    renderList({ drivers, predictions: preds, positions: pos });
    expect(within(screen.getByTestId("row-NOR")).getByTestId("podium-bar")).toHaveStyle({ width: "42%" });
  });
});

describe("Timing list — fastest lap colouring", () => {
  // Example: two drivers
  it("colours VER's last lap purple and HAM's green at lap 10", () => {
    const laps: LapRow[] = [];
    for (let lap = 1; lap <= 10; lap++) {
      laps.push(lapRow("VER", lap, lap === 10 ? 95.9 : 97 + lap / 10));
      laps.push(lapRow("HAM", lap, lap === 10 ? 96.2 : 97.5 + lap / 10));
    }
    renderList({
      lap: 10,
      laps,
      drivers: [driver("VER", 1, { last_lap_time_s: 95.9 }), driver("HAM", 2, { last_lap_time_s: 96.2 })],
    });
    expect(field("VER", "last")).toHaveClass("text-purple-400");
    expect(field("VER", "last")).toHaveTextContent("1:35.900");
    expect(field("HAM", "last")).toHaveClass("text-emerald-400");
    expect(field("HAM", "last")).not.toHaveClass("text-purple-400");
  });

  it("ignores laps after the current lap", () => {
    const laps = [
      lapRow("VER", 2, 96),
      lapRow("VER", 3, 97),
      lapRow("HAM", 2, 98),
      lapRow("HAM", 3, 95), // after the current lap 2: must not count
    ];
    renderList({
      lap: 2,
      laps,
      drivers: [driver("VER", 1, { last_lap_time_s: 96 }), driver("HAM", 2, { last_lap_time_s: 98 })],
    });
    expect(field("VER", "last")).toHaveClass("text-purple-400");
    expect(field("HAM", "last")).toHaveClass("text-emerald-400");
  });

  it("leaves a last lap uncoloured when it is slower than the driver's best", () => {
    const laps = [lapRow("VER", 2, 96), lapRow("VER", 3, 97)];
    renderList({ lap: 3, laps, drivers: [driver("VER", 1, { last_lap_time_s: 97 })] });
    expect(field("VER", "last").className).not.toMatch(/text-(purple|emerald)-400/);
  });
});

describe("Timing list — focus", () => {
  it("clicking a row calls the focus setter with that code", () => {
    const onFocus = vi.fn();
    renderList({ drivers: [driver("VER", 1), driver("NOR", 2)], onFocus });
    fireEvent.click(screen.getByTestId("row-NOR"));
    expect(onFocus).toHaveBeenCalledWith("NOR");
  });
});
