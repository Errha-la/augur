import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { clearRequestCache } from "../../api/requestCache";
import type { DegradationResponse } from "../../api/types";
import { driver } from "../../test/builders";
import { Pace, PaceDriversPicker, paceDrivers, paceModel, PaceView, togglePaceDriver } from "./Pace";

afterEach(() => {
  clearRequestCache();
  vi.unstubAllGlobals();
});

const drivers = [
  driver("NOR", 1, { team: "McLaren", team_color: "#FF8000" }),
  driver("LEC", 2, { team: "Ferrari", team_color: "#E8002D" }),
  driver("PIA", 3, { team: "McLaren", team_color: "#FF8000" }),
  driver("VER", 4, { team: "Red Bull" }),
];

function deg(codes: string[]): DegradationResponse {
  return {
    race_id: "r",
    lap: 20,
    compounds: [
      {
        compound: "MEDIUM",
        fit: null,
        points: codes.flatMap((code) => [5, 6, 8].map((lap) => ({ code, lap, tyre_age: lap, fuel_corrected_s: 89 + lap / 10 }))),
      },
    ],
  };
}

describe("Pace comparison widget", () => {
  it("Follow focus: empty setting, focus LEC, order NOR, LEC, PIA plots NOR, LEC and PIA", () => {
    expect(paceDrivers(undefined, drivers, "LEC")).toEqual({ codes: ["NOR", "LEC", "PIA"], missing: [] });
    expect(paceDrivers([], drivers, "NOR").codes).toEqual(["NOR", "LEC"]);
  });

  it("Four drivers at most: toggling HAM onto VER, NOR, LEC, PIA leaves the setting unchanged", () => {
    const full = ["VER", "NOR", "LEC", "PIA"];
    expect(togglePaceDriver(full, "HAM")).toEqual(full);
    expect(togglePaceDriver(full, "NOR")).toEqual(["VER", "LEC", "PIA"]);
    expect(togglePaceDriver(undefined, "NOR")).toEqual(["NOR"]);

    const onChange = vi.fn();
    render(<PaceDriversPicker value={["NOR", "LEC", "PIA", "VER"]} drivers={[...drivers, driver("HAM", 5)]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Drivers for Pace compare widget" }));
    const ham = screen.getByRole("menuitemcheckbox", { name: "HAM" });
    expect(ham).toBeDisabled();
    fireEvent.click(ham);
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Follow focus" }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("Pinned driver missing: SAR and NOR in a race without SAR shows the message and plots NOR", async () => {
    expect(paceDrivers(["SAR", "NOR"], drivers, "LEC")).toEqual({ codes: ["NOR"], missing: ["SAR"] });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(deg(["NOR", "LEC"])), { status: 200 })));
    const ctx = { raceId: "r", lap: 20, totalLaps: 58, playing: false, focusCode: "LEC", drivers };
    render(<Pace ctx={ctx} setting={["SAR", "NOR"]} size={{ width: 500, height: 300 }} />);
    expect(screen.getByTestId("pace-missing")).toHaveTextContent("SAR not in this race");
    expect(await screen.findByTestId("pace-legend-NOR")).toBeInTheDocument();
    expect(screen.queryByTestId("pace-legend-LEC")).not.toBeInTheDocument();
  });

  it("only pins outside the race: follows the focus driver", () => {
    expect(paceDrivers(["SAR"], drivers, "VER")).toEqual({ codes: ["PIA", "VER"], missing: ["SAR"] });
  });

  it("rows by lap with gaps, teammates' second driver dashed, caption shown", () => {
    const model = paceModel(deg(["NOR", "PIA"]), ["NOR", "PIA"], drivers);
    expect(model.rows.map((r) => r.lap)).toEqual([5, 6, 8]);
    expect(model.series.map((s) => [s.code, s.dashed])).toEqual([
      ["NOR", false],
      ["PIA", true],
    ]);
    render(<PaceView data={deg(["NOR"])} codes={["NOR"]} drivers={drivers} lap={20} size={{ width: 400, height: 200 }} />);
    expect(screen.getByText("Fuel-corrected clean laps")).toBeInTheDocument();
  });

  it("no points for the drivers: 'No clean laps for <codes> yet'", () => {
    render(<PaceView data={deg(["VER"])} codes={["NOR", "LEC"]} drivers={drivers} lap={2} />);
    expect(screen.getByTestId("chart-message")).toHaveTextContent("No clean laps for NOR, LEC yet");
  });
});
