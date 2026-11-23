import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { clearRequestCache } from "../../api/requestCache";
import type { TraceResponse } from "../../api/types";
import { RaceTrace, RaceTraceView, traceCaption, traceModel } from "./RaceTrace";

afterEach(() => {
  clearRequestCache();
  vi.unstubAllGlobals();
});

const SIZE = { width: 600, height: 300 };

function trace(reference: number | null): TraceResponse {
  return {
    race_id: "r",
    lap: 3,
    reference_lap_s: reference,
    drivers: [
      { code: "NOR", team_color: "#FF8000", points: [1, 2, 3].map((lap) => ({ lap, delta_s: 0.5 * lap })) },
      { code: "LEC", team_color: null, points: [1, 3].map((lap) => ({ lap, delta_s: -0.5 * lap })) },
    ],
  };
}

describe("Race trace widget", () => {
  it("Reference pace caption: 90.993 reads 'Reference pace 1:30.993'", () => {
    expect(traceCaption(90.993)).toBe("Reference pace 1:30.993");
    render(<RaceTraceView data={trace(90.993)} focusCode="LEC" size={SIZE} />);
    expect(screen.getByTestId("chart-caption")).toHaveTextContent("Reference pace 1:30.993");
  });

  it("No laps yet: a null reference shows 'No laps yet'", () => {
    render(<RaceTraceView data={trace(null)} focusCode="NOR" size={SIZE} />);
    expect(screen.getByTestId("chart-message")).toHaveTextContent("No laps yet");
  });

  it("one series per driver in team colours, the focus driver thicker; rows by lap with gaps kept", () => {
    const model = traceModel(trace(90), "LEC");
    expect(model.series.map((s) => [s.code, s.color, s.strokeWidth > 2])).toEqual([
      ["NOR", "#FF8000", false],
      ["LEC", "#a1a1aa", true],
    ]);
    expect(model.rows).toEqual([
      { lap: 1, NOR: 0.5, LEC: -0.5 },
      { lap: 2, NOR: 1 },
      { lap: 3, NOR: 1.5, LEC: -1.5 },
    ]);
  });

  it("fetches /trace for the replay lap", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(trace(88.5)), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const ctx = { raceId: "r", lap: 3, totalLaps: 58, playing: false, focusCode: "NOR", drivers: [] };
    render(<RaceTrace ctx={ctx} size={SIZE} />);
    expect(await screen.findByText(/Reference pace 1:28.500/)).toBeInTheDocument();
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toBe("/api/races/r/trace?lap=3");
  });
});
