import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchDegradation,
  fetchPitWindow,
  fetchPositionDistribution,
  fetchRejoin,
  fetchStints,
  fetchTrace,
} from "./client";
import { clearRequestCache } from "./requestCache";

afterEach(() => {
  clearRequestCache();
  vi.unstubAllGlobals();
});

function stubFetch(body: unknown = { ok: true }) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(body), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function urlOf(fetchMock: ReturnType<typeof stubFetch>, call = 0): string {
  return String((fetchMock.mock.calls[call] as unknown[])[0]);
}

const RACE = "2024-24-abu-dhabi-grand-prix";

describe("strategy chart client", () => {
  it.each([
    ["trace", () => fetchTrace(RACE, 58), `/api/races/${RACE}/trace?lap=58`],
    ["rejoin", () => fetchRejoin(RACE, 20, "NOR"), `/api/races/${RACE}/rejoin?lap=20&driver=NOR`],
    ["pit-window", () => fetchPitWindow(RACE, 20, "LEC"), `/api/races/${RACE}/pit-window?lap=20&driver=LEC`],
    ["stints", () => fetchStints(RACE, 30), `/api/races/${RACE}/stints?lap=30`],
    ["degradation", () => fetchDegradation(RACE, 30), `/api/races/${RACE}/degradation?lap=30`],
    [
      "positions/distribution",
      () => fetchPositionDistribution(RACE, 5),
      `/api/races/${RACE}/positions/distribution?lap=5`,
    ],
  ])("requests %s with the lap (and driver) and passes the body through", async (_name, call, url) => {
    const body = { race_id: RACE, marker: _name };
    const fetchMock = stubFetch(body);
    await expect(call()).resolves.toEqual(body);
    expect(urlOf(fetchMock)).toBe(url);
  });

  it("sends one request for two identical calls", async () => {
    const fetchMock = stubFetch({ race_id: RACE });
    await Promise.all([fetchPitWindow(RACE, 20, "NOR"), fetchPitWindow(RACE, 20, "NOR")]);
    await fetchPitWindow(RACE, 20, "NOR");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await fetchPitWindow(RACE, 20, "PIA");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("rejects bad laps and empty drivers before any request", () => {
    const fetchMock = stubFetch();
    expect(() => fetchTrace(RACE, 0)).toThrow(RangeError);
    expect(() => fetchStints(RACE, 1.5)).toThrow(RangeError);
    expect(() => fetchRejoin(RACE, 3, "")).toThrow(RangeError);
    expect(() => fetchPitWindow(RACE, 3, "")).toThrow(RangeError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces HTTP errors and does not keep them", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchDegradation(RACE, 4)).rejects.toMatchObject({ name: "ApiError", status: 500 });
    await expect(fetchDegradation(RACE, 4)).rejects.toMatchObject({ status: 500 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
