import { render, renderHook, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChartBody, type ChartSchedule, useChartData } from "./useChartData";

function hook(schedule: ChartSchedule, fetcher: (lap: number) => Promise<unknown>, start: number, playing: boolean) {
  return renderHook(
    ({ lap, playing: p, raceId }) => useChartData({ raceId, lap, playing: p }, schedule, ["NOR"], () => fetcher(lap)),
    { initialProps: { lap: start, playing, raceId: "r1" } },
  );
}

async function play(view: ReturnType<typeof hook>, from: number, to: number) {
  for (let lap = from; lap <= to; lap++) {
    view.rerender({ lap, playing: true, raceId: "r1" });
    await Promise.resolve();
  }
}

describe("Chart widget loading, errors, and request schedule", () => {
  it("Pit window during playback: laps 11 to 16 send one request, for lap 15, and keep it on screen", async () => {
    const fetcher = vi.fn(async (lap: number) => ({ lap }));
    const view = hook("refresh", fetcher, 11, true);
    await play(view, 12, 16);
    expect(fetcher.mock.calls.map(([lap]) => lap)).toEqual([15]);
    await waitFor(() => expect(view.result.current.data).toEqual({ lap: 15 }));
  });

  it("requests at once when paused on the refresh schedule", () => {
    const fetcher = vi.fn(async (lap: number) => ({ lap }));
    hook("refresh", fetcher, 13, false);
    expect(fetcher.mock.calls.map(([lap]) => lap)).toEqual([13]);
  });

  it("Stints every lap: laps 11 to 13 send requests for laps 12 and 13", async () => {
    const fetcher = vi.fn(async (lap: number) => ({ lap }));
    const view = hook("lap", fetcher, 11, true);
    await play(view, 12, 13);
    expect(fetcher.mock.calls.map(([lap]) => lap)).toEqual([11, 12, 13]);
  });

  it("does not return a response from another race", async () => {
    const fetcher = vi.fn(async (lap: number) => ({ lap }));
    const view = hook("refresh", fetcher, 20, false);
    await waitFor(() => expect(view.result.current.data).toEqual({ lap: 20 }));
    view.rerender({ lap: 21, playing: true, raceId: "r2" });
    expect(view.result.current.data).toBeNull();
  });

  it("Failed request: shows 'Could not load Race trace', then requests again at the next lap", async () => {
    const fetcher = vi.fn(async (lap: number) => {
      if (lap === 20) throw new Error("HTTP 500");
      return { lap };
    });
    function Trace({ lap }: { lap: number }) {
      const state = useChartData({ raceId: "r1", lap, playing: false }, "lap", [], () => fetcher(lap));
      return (
        <ChartBody title="Race trace" state={state}>
          {(d: { lap: number }) => <p>lap {d.lap}</p>}
        </ChartBody>
      );
    }
    const view = render(<Trace lap={20} />);
    expect(screen.getByTestId("chart-message")).toHaveTextContent("Loading...");
    await screen.findByText("Could not load Race trace");
    view.rerender(<Trace lap={21} />);
    await screen.findByText("lap 21");
    expect(fetcher.mock.calls.map(([lap]) => lap)).toEqual([20, 21]);
  });
});
