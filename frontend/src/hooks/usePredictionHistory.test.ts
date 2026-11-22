import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ABU_DHABI, BAHRAIN, fakeBackend } from "../test/fakeBackend";
import { usePredictionHistory } from "./usePredictionHistory";

function predictionLaps(backend: ReturnType<typeof fakeBackend>) {
  return backend.of("predictions").map((r) => r.lap);
}

describe("usePredictionHistory", () => {
  // specs/chart-predictions — Scenario: Cached history
  it("requests only /predictions?lap=10 and 11 when moving from lap 10 to 12", async () => {
    const backend = fakeBackend();
    const { result, rerender } = renderHook(({ lap }) => usePredictionHistory(ABU_DHABI, lap), {
      initialProps: { lap: 10 },
    });
    // Chart laps 2..10 need predictions made at laps 1..9.
    await waitFor(() => expect(result.current.size).toBe(9));
    expect([...predictionLaps(backend)].sort((a, b) => a - b)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);

    backend.requests.length = 0;
    rerender({ lap: 12 });
    await waitFor(() => expect(result.current.size).toBe(11));
    expect([...predictionLaps(backend)].sort((a, b) => a - b)).toEqual([10, 11]);
    expect(Math.max(...predictionLaps(backend))).toBeLessThan(12);
  });

  it("stores predicted_next_lap_s per driver under the lap it was predicted at", async () => {
    fakeBackend();
    const { result } = renderHook(() => usePredictionHistory(ABU_DHABI, 3));
    await waitFor(() => expect(result.current.size).toBe(2));
    const atLap1 = result.current.get(1)!;
    expect(Object.keys(atLap1).length).toBeGreaterThan(0);
    for (const v of Object.values(atLap1)) expect(v === null || typeof v === "number").toBe(true);
  });

  it("requests nothing at lap 1 and starts a fresh cache for another race", async () => {
    const backend = fakeBackend();
    const { result, rerender } = renderHook(({ race, lap }) => usePredictionHistory(race, lap), {
      initialProps: { race: ABU_DHABI, lap: 1 },
    });
    expect(predictionLaps(backend)).toEqual([]);
    rerender({ race: ABU_DHABI, lap: 3 });
    await waitFor(() => expect(result.current.size).toBe(2));
    backend.requests.length = 0;
    rerender({ race: BAHRAIN, lap: 3 });
    await waitFor(() => expect(predictionLaps(backend).sort()).toEqual([1, 2]));
    expect(backend.of("predictions").every((r) => r.raceId === BAHRAIN)).toBe(true);
  });
});
