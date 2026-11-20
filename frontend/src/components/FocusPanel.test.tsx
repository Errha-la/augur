import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { LapData, LapRow } from "../api/types";
import { driver, lapRow, positions, prediction, raceEvent } from "../test/builders";
import { ABU_DHABI, fakeBackend, fixtures } from "../test/fakeBackend";
import { advance, goToLap, renderApp, waitForShown } from "../test/renderApp";
import { FocusPanel, GREEN_RACE_NOTE } from "./FocusPanel";

function lapData(lap: number, extra: Partial<LapData> = {}): LapData {
  return {
    raceId: ABU_DHABI,
    lap,
    state: { ...fixtures.state, lap, drivers: [driver("VER", 1), driver("HAM", 5, { team: "Mercedes" })] },
    laps: [],
    predictions: { race_id: ABU_DHABI, lap, drivers: [prediction("HAM", { deg_s_per_lap: 0.041, cliff: true })] },
    events: { race_id: ABU_DHABI, lap, model: "lightgbm", analyzed: true, commentary_model: null, events: [] },
    positions: { ...fixtures.positions, lap, drivers: [positions("HAM")] },
    ...extra,
  };
}

function renderPanel(data: LapData, playing = false) {
  return render(<FocusPanel data={data} focusCode="HAM" playing={playing} chartSize={{ width: 300, height: 100 }} />);
}

describe("Focus driver panel", () => {
  beforeEach(() => {
    fakeBackend();
  });

  // Example: two stints
  it("draws a MEDIUM segment of 18 laps and a HARD segment of 7 laps at lap 25", () => {
    const laps: LapRow[] = [];
    for (let n = 1; n <= 30; n++) {
      laps.push(n <= 18 ? lapRow("HAM", n, 90, { stint: 1, compound: "MEDIUM" }) : lapRow("HAM", n, 91, { stint: 2, compound: "HARD" }));
    }
    renderPanel(lapData(25, { laps }));
    const segments = screen.getAllByTestId("stint-segment");
    expect(segments.map((s) => [s.dataset.compound, s.dataset.laps])).toEqual([
      ["MEDIUM", "18"],
      ["HARD", "7"],
    ]);
    expect(segments[0]).toHaveStyle({ flexGrow: "18" });
  });

  // Example: P5 driver at lap 30
  it("shows P4.6 (P3-P7), WIN 4%, PODIUM 31%, POINTS 99% and the green-race note", () => {
    const data = lapData(30, {
      positions: {
        ...fixtures.positions,
        lap: 30,
        drivers: [
          positions("HAM", { expected_position: 4.6, position_p10: 3, position_p90: 7, p_win: 0.04, p_podium: 0.31, p_points: 0.99 }),
        ],
      },
    });
    renderPanel(data);
    expect(screen.getByTestId("focus-expected")).toHaveTextContent("P4.6 (P3-P7)");
    const probs = screen.getByTestId("focus-probabilities");
    expect(probs).toHaveTextContent("WIN 4%");
    expect(probs).toHaveTextContent("PODIUM 31%");
    expect(probs).toHaveTextContent("POINTS 99%");
    expect(screen.getByText(GREEN_RACE_NOTE)).toBeInTheDocument();
  });

  it("shows code, team, degradation with cliff, and only the driver's events", () => {
    const events = [raceEvent("e2", 12, "pace_drop", ["VER"]), raceEvent("e1", 10, "undercut_window", ["VER", "HAM"])];
    renderPanel(lapData(12, { events: { race_id: ABU_DHABI, lap: 12, model: "m", analyzed: true, commentary_model: null, events } }));
    const panel = screen.getByTestId("focus-panel");
    expect(panel).toHaveTextContent("HAM");
    expect(panel).toHaveTextContent("Mercedes");
    expect(screen.getByTestId("focus-deg")).toHaveTextContent("+0.041/lap");
    expect(panel).toHaveTextContent("CLIFF");
    const list = screen.getByTestId("focus-events");
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    expect(list).toHaveTextContent("UNDERCUT");
  });

  it("shows the dash icon for null probabilities and a null p10-p90 range", async () => {
    fakeBackend({
      handlers: {
        strategy: (ctx) => ({
          ...fixtures.strategy,
          ...ctx,
          strategies: [{ name: "no further stop", pit_lap: null, mean_s: 3600, p10_s: null, p90_s: null, win_probability: 0.5 }],
        }),
      },
    });
    const data = lapData(10, {
      positions: { ...fixtures.positions, lap: 10, drivers: [positions("HAM", { p_win: null, p_podium: null, p_points: null })] },
    });
    renderPanel(data);
    expect(within(screen.getByTestId("focus-probabilities")).getAllByTestId("dash")).toHaveLength(3);
    const table = await screen.findByTestId("strategy-table");
    expect(within(table).getAllByTestId("dash")).toHaveLength(1);
    expect(table).not.toHaveTextContent("–");
  });

  it("shows Simulating... until the strategy arrives, then the table", async () => {
    renderPanel(lapData(15));
    expect(screen.getByTestId("simulating")).toBeInTheDocument();
    const table = await screen.findByTestId("strategy-table");
    expect(table).toHaveTextContent("pit on lap 23");
    expect(table).toHaveTextContent("1:03:50.998");
    expect(table).toHaveTextContent("100%");
  });
});

describe("Focus driver panel — Strategy requests during playback", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  it("requests strategy and probability history for lap 15 only while playing 11 → 16", async () => {
    // No events, so the intelligence panel's event strategy requests stay out of this count.
    const { backend } = await renderApp({
      handlers: { events: ({ raceId, lap }) => ({ race_id: raceId, lap, model: "m", analyzed: true, commentary_model: null, events: [] }) },
    });
    await goToLap(11);
    await waitFor(() => expect(backend.of("strategy").some((r) => r.lap === 11)).toBe(true));
    const before = backend.requests.length;

    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    for (let lap = 12; lap <= 16; lap++) {
      await advance(1000);
      await waitForShown(lap);
    }
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    const during = backend.requests.slice(before).filter((r) => r.lap <= 16);
    const strategyLaps = during.filter((r) => r.endpoint === "strategy").map((r) => r.lap);
    const historyLaps = during.filter((r) => r.endpoint === "positions/history").map((r) => r.lap);
    // Pausing at lap 16 refreshes lap 16; during playback only lap 15 was requested.
    expect(strategyLaps.filter((l) => l < 16)).toEqual([15]);
    expect(historyLaps.filter((l) => l < 16)).toEqual([15]);
  });

  it("does not show the previous driver's strategy error after a focus change during playback", async () => {
    fakeBackend({
      handlers: {
        strategy: (ctx) => (ctx.driver === "VER" ? new Response("boom", { status: 500 }) : { ...fixtures.strategy, ...ctx }),
      },
    });
    const size = { width: 300, height: 100 };
    const { rerender } = render(<FocusPanel data={lapData(12)} focusCode="VER" playing={false} chartSize={size} />);
    expect(await screen.findByText(/Strategy unavailable/)).toHaveTextContent("driver=VER");

    rerender(<FocusPanel data={lapData(13)} focusCode="HAM" playing chartSize={size} />);
    expect(screen.queryByText(/Strategy unavailable/)).not.toBeInTheDocument();
    expect(screen.getByText("Strategy updates at lap 15 or when paused")).toBeInTheDocument();
  });

  it("does not show Simulating... for a new focus driver while the previous driver's request runs", async () => {
    const backend = fakeBackend({ manual: true });
    const size = { width: 300, height: 100 };
    const { rerender } = render(<FocusPanel data={lapData(15)} focusCode="VER" playing chartSize={size} />);
    await waitFor(() => expect(backend.of("strategy")).toHaveLength(1));
    expect(screen.getByTestId("simulating")).toBeInTheDocument();

    rerender(<FocusPanel data={lapData(16)} focusCode="HAM" playing chartSize={size} />);
    expect(screen.queryByTestId("simulating")).not.toBeInTheDocument();
    expect(screen.getByText("Strategy updates at lap 20 or when paused")).toBeInTheDocument();
  });

  it("keeps a slow lap-15 strategy response when playback moves on to lap 16", async () => {
    const backend = fakeBackend({ manual: true });
    const { rerender } = render(
      <FocusPanel data={lapData(15)} focusCode="HAM" playing chartSize={{ width: 300, height: 100 }} />,
    );
    await waitFor(() => expect(backend.of("strategy")).toHaveLength(1));
    rerender(<FocusPanel data={lapData(16)} focusCode="HAM" playing chartSize={{ width: 300, height: 100 }} />);
    expect(backend.of("strategy")[0].signal?.aborted).toBe(false);
    backend.release();
    expect(await screen.findByTestId("strategy-table")).toHaveTextContent("AT LAP 15");
  });
});
