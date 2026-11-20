import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { api } from "../api/client";
import { ABU_DHABI, fakeBackend } from "../test/fakeBackend";
import { useLapData } from "./useLapData";

const LAP_ENDPOINTS = ["state", "laps", "predictions", "events", "positions"] as const;

describe("useLapData", () => {
  it("fetches the five lap endpoints in parallel and publishes them together", async () => {
    const backend = fakeBackend({ manual: true });
    const { result } = renderHook(() => useLapData(ABU_DHABI, 5));

    await waitFor(() => expect(backend.requests).toHaveLength(5));
    expect(backend.requests.map((r) => r.endpoint).sort()).toEqual([...LAP_ENDPOINTS].sort());

    // Four of five arrived: nothing is published yet.
    await act(async () => backend.release((r) => r.endpoint !== "positions"));
    expect(result.current.data).toBeNull();
    expect(result.current.pending).toBe(true);

    await act(async () => backend.release());
    await waitFor(() => expect(result.current.data?.lap).toBe(5));
    expect(result.current.pending).toBe(false);
    expect(result.current.data?.state.lap).toBe(5);
    expect(result.current.data?.positions.lap).toBe(5);
  });

  // specs/replay-controls — Scenario: Fast slider move
  it("shows only lap 40 after a fast slider move from 5 to 40", async () => {
    const backend = fakeBackend({ manual: true });
    const published: number[] = [];
    const { result, rerender } = renderHook(({ lap }) => useLapData(ABU_DHABI, lap), {
      initialProps: { lap: 5 },
    });
    for (let lap = 6; lap <= 40; lap++) rerender({ lap });

    await waitFor(() => expect(backend.requests.some((r) => r.lap === 40)).toBe(true));
    const earlier = backend.requests.filter((r) => r.lap < 40);
    expect(earlier.length).toBeGreaterThan(0);
    expect(earlier.every((r) => r.signal?.aborted)).toBe(true);

    // Release lap 40 first, then every older response that is still held.
    await act(async () => backend.release((r) => r.lap === 40));
    await waitFor(() => expect(result.current.data?.lap).toBe(40));
    published.push(result.current.data!.lap);
    await act(async () => backend.release());
    published.push(result.current.data!.lap);

    expect(published).toEqual([40, 40]);
    expect(result.current.data?.state.lap).toBe(40);
  });

  // specs/replay-controls — Scenario: No future requests
  it("never requests a lap above the lap on screen", async () => {
    const backend = fakeBackend();
    const { result, rerender } = renderHook(({ lap }) => useLapData(ABU_DHABI, lap), {
      initialProps: { lap: 12 },
    });
    await waitFor(() => expect(result.current.data?.lap).toBe(12));
    expect(backend.requests.every((r) => r.lap <= 12)).toBe(true);

    rerender({ lap: 3 });
    await waitFor(() => expect(result.current.data?.lap).toBe(3));
    const after = backend.requests.slice(5);
    expect(after.every((r) => r.lap <= 3)).toBe(true);
    expect(result.current.data?.laps.every((r) => r.lap <= 3)).toBe(true);
    expect(result.current.data?.events.events.every((e) => e.lap <= 3)).toBe(true);
  });

  it("reports a failed lap as an error and keeps the last complete lap", async () => {
    let fail = false;
    fakeBackend({
      handlers: {
        positions: ({ lap }) => (fail ? new Response("boom", { status: 500 }) : { lap, drivers: [] }),
      },
    });
    const { result, rerender } = renderHook(({ lap }) => useLapData(ABU_DHABI, lap), {
      initialProps: { lap: 2 },
    });
    await waitFor(() => expect(result.current.data?.lap).toBe(2));
    fail = true;
    rerender({ lap: 3 });
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.data?.lap).toBe(2);
    expect(result.current.pending).toBe(false);
  });
});

describe("api client", () => {
  it("rejects invalid laps and encodes path parameters", async () => {
    const backend = fakeBackend();
    expect(() => api.state(ABU_DHABI, 0)).toThrow(RangeError);
    expect(() => api.state(ABU_DHABI, 1.5)).toThrow(RangeError);
    expect(() => api.strategy(ABU_DHABI, 3, "")).toThrow(RangeError);
    await api.strategy("a/b", 3, "N&R");
    expect(backend.requests[0].url).toBe("/api/races/a%2Fb/strategy?lap=3&driver=N%26R");
  });
});
