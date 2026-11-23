import { describe, expect, it } from "vitest";
import type { DriverState } from "../api/types";
import { driver, lapRow } from "../test/builders";
import { chartModel } from "./chartModel";

// race-overview "Lap-time chart": non-racing laps, pit markers, neutralised laps, y-axis.

const ferrari = "#E8002D";
const mercedes = "#27F4D2";

function abuDhabi(): DriverState[] {
  return [
    driver("NOR", 1, { team: "McLaren", team_color: "#FF8000" }),
    driver("SAI", 2, { team: "Ferrari", team_color: ferrari }),
    driver("LEC", 3, { team: "Ferrari", team_color: ferrari }),
    driver("RUS", 4, { team: "Mercedes", team_color: mercedes }),
  ];
}

describe("Lap-time chart — Non-racing laps leave the line", () => {
  it("hides LEC's lap 1, VSC lap 2, pit-in lap 20 and pit-out lap 21 (example: LEC at Abu Dhabi 2024, lap 40)", () => {
    const laps = [
      lapRow("LEC", 1, 98.031, { track_status: "2" }),
      lapRow("LEC", 2, 113.013, { track_status: "6" }),
      lapRow("LEC", 4, 89.273),
      lapRow("LEC", 20, 92.189, { pit_in: true }),
      lapRow("LEC", 21, 108.662, { pit_out: true }),
      lapRow("LEC", 22, 89.802),
    ];
    const model = chartModel(abuDhabi(), laps, "LEC", 40);
    const at = (n: number) => model.rows[n - 1].LEC;
    expect([at(1), at(2), at(4), at(20), at(21), at(22)]).toEqual([null, null, 89.273, null, null, 89.802]);
  });

  it("hides safety-car and red-flag laps too", () => {
    const laps = [lapRow("LEC", 5, 120, { track_status: "4" }), lapRow("LEC", 6, 130, { track_status: "5" }), lapRow("LEC", 7, 90)];
    const model = chartModel(abuDhabi(), laps, "LEC", 7);
    expect(model.rows.slice(4).map((r) => r.LEC)).toEqual([null, null, 90]);
  });

  it("treats a null or unknown track status as a racing lap", () => {
    const laps = [lapRow("LEC", 5, 90, { track_status: null }), lapRow("LEC", 6, 91, { track_status: "7" })];
    const model = chartModel(abuDhabi(), laps, "LEC", 6);
    expect(model.rows.slice(4).map((r) => r.LEC)).toEqual([90, 91]);
  });
});

describe("Lap-time chart — Pit stop markers", () => {
  it("marks LEC 20, SAI 25, RUS 26 in each driver's line colour", () => {
    const laps = [
      lapRow("LEC", 20, 92.189, { pit_in: true }),
      lapRow("LEC", 21, 108.662, { pit_out: true }),
      lapRow("SAI", 25, 90.842, { pit_in: true }),
      lapRow("RUS", 26, 92.057, { pit_in: true }),
      lapRow("NOR", 27, 91, { pit_in: true }), // not plotted: NOR is not LEC's neighbour
    ];
    const model = chartModel(abuDhabi(), laps, "LEC", 40);
    expect(model.pitMarkers).toEqual([
      { lap: 20, code: "LEC", color: ferrari },
      { lap: 25, code: "SAI", color: ferrari },
      { lap: 26, code: "RUS", color: mercedes },
    ]);
  });

  it("draws no marker after the current lap", () => {
    const laps = [lapRow("LEC", 20, 92.189, { pit_in: true })];
    expect(chartModel(abuDhabi(), laps, "LEC", 19).pitMarkers).toEqual([]);
  });
});

describe("Lap-time chart — Safety-car and VSC shading", () => {
  it("shades VSC laps 2 and 3 from any driver's rows", () => {
    const laps = [
      lapRow("NOR", 2, 110, { track_status: "6" }),
      lapRow("LEC", 2, 113, { track_status: "6" }),
      lapRow("NOR", 3, 100, { track_status: "6" }),
      lapRow("LEC", 3, 99.6, { track_status: "1" }),
      lapRow("LEC", 4, 89.3),
    ];
    expect(chartModel(abuDhabi(), laps, "LEC", 10).neutralised).toEqual([
      { lap: 2, label: "VSC", showLabel: true },
      { lap: 3, label: "VSC", showLabel: false },
    ]);
  });

  it("labels each run of same-label laps once, on its first lap", () => {
    const status: Record<number, string> = { 5: "4", 6: "4", 7: "6", 9: "6", 10: "6" };
    const laps = Object.entries(status).map(([n, s]) => lapRow("NOR", Number(n), 110, { track_status: s }));
    expect(chartModel(abuDhabi(), laps, "LEC", 12).neutralised).toEqual([
      { lap: 5, label: "SC", showLabel: true },
      { lap: 6, label: "SC", showLabel: false },
      { lap: 7, label: "VSC", showLabel: true },
      { lap: 9, label: "VSC", showLabel: true },
      { lap: 10, label: "VSC", showLabel: false },
    ]);
  });

  it.each([
    [["1", "1", "2"], null],
    [["1", "6", "6"], "VSC"],
    [["6", "4"], "SC"],
    [["4", "5"], "RED"],
  ])("labels a lap with statuses %j as %s (example: label per lap)", (statuses, label) => {
    const codes = ["NOR", "SAI", "LEC"];
    const laps = statuses.map((s, i) => lapRow(codes[i], 5, 95, { track_status: s }));
    const model = chartModel(abuDhabi(), laps, "LEC", 10);
    expect(model.neutralised).toEqual(label ? [{ lap: 5, label, showLabel: true }] : []);
  });

  it("shades no lap after the current lap", () => {
    const laps = [lapRow("NOR", 12, 120, { track_status: "4" })];
    expect(chartModel(abuDhabi(), laps, "LEC", 11).neutralised).toEqual([]);
  });
});

describe("Lap-time chart — Y-axis from racing laps", () => {
  it("is [87, 92] for racing laps 88.2-91.0 s (median 89.0) whatever the hidden out-laps are", () => {
    const racing = [88.2, 88.6, 89.0, 89.4, 91.0];
    const laps = [
      ...racing.map((t, i) => lapRow("LEC", i + 2, t)),
      lapRow("LEC", 10, 108.7, { pit_out: true }),
      lapRow("SAI", 11, 108.7, { pit_out: true }),
    ];
    expect(chartModel(abuDhabi(), laps, "LEC", 12).domain).toEqual([87, 92]);
  });

  it("has no domain when every plotted lap is hidden", () => {
    const laps = [lapRow("LEC", 1, 98)];
    expect(chartModel(abuDhabi(), laps, "LEC", 1).domain).toBeNull();
  });
});
