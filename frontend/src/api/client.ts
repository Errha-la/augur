import type {
  EventsResponse,
  LapData,
  LapRow,
  PositionsHistoryResponse,
  PositionsResponse,
  PredictionsResponse,
  RaceState,
  RaceSummary,
  SettingsResponse,
  SettingsUpdate,
  StrategyResponse,
  WrappedResponse,
} from "./types";
import { sharedGet } from "./requestCache";

/** Relative base: the Vite dev server proxies /api to the backend. */
export const API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly url: string;

  constructor(status: number, url: string) {
    super(`GET ${url} failed with HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.url = url;
  }
}

export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function assertLap(lap: number): void {
  // A bad lap must fail loudly here instead of becoming `lap=NaN` in a URL.
  if (!Number.isInteger(lap) || lap < 1) {
    throw new RangeError(`lap must be a positive integer, got ${lap}`);
  }
}

function raceUrl(raceId: string, path: string, params: Record<string, string | number>): string {
  if (!raceId) throw new RangeError("raceId must be a non-empty string");
  const query = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]));
  return `${API_BASE}/races/${encodeURIComponent(raceId)}/${path}?${query}`;
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) throw new ApiError(res.status, url);
  return (await res.json()) as T;
}

function lapGet<T>(path: string) {
  return (raceId: string, lap: number, signal?: AbortSignal): Promise<T> => {
    assertLap(lap);
    return getJson<T>(raceUrl(raceId, path, { lap }), signal);
  };
}

/** A settings update the server rejected (HTTP 422); `detail` is shown next to Save. */
export class SettingsRejected extends Error {
  readonly detail: string;

  constructor(detail: string) {
    super(detail);
    this.name = "SettingsRejected";
    this.detail = detail;
  }
}

async function putSettings(update: SettingsUpdate, signal?: AbortSignal): Promise<SettingsResponse> {
  const url = `${API_BASE}/settings`;
  const res = await fetch(url, {
    method: "PUT",
    signal,
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (res.status === 422) {
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    throw new SettingsRejected(typeof body?.detail === "string" ? body.detail : "Settings rejected");
  }
  if (!res.ok) throw new ApiError(res.status, url);
  return (await res.json()) as SettingsResponse;
}

export const api = {
  races: (signal?: AbortSignal) => getJson<RaceSummary[]>(`${API_BASE}/races`, signal),
  settings: (signal?: AbortSignal) => getJson<SettingsResponse>(`${API_BASE}/settings`, signal),
  putSettings,
  state: lapGet<RaceState>("state"),
  laps: lapGet<LapRow[]>("laps"),
  predictions: lapGet<PredictionsResponse>("predictions"),
  events: lapGet<EventsResponse>("events"),
  positions: lapGet<PositionsResponse>("positions"),
  /** Shared between widgets (see requestCache). */
  positionsHistory(raceId: string, lap: number, signal?: AbortSignal): Promise<PositionsHistoryResponse> {
    assertLap(lap);
    const url = raceUrl(raceId, "positions/history", { lap });
    return sharedGet(url, (s) => getJson<PositionsHistoryResponse>(url, s), signal);
  },
  /** Shared between widgets (see requestCache). */
  strategy(raceId: string, lap: number, driver: string, signal?: AbortSignal): Promise<StrategyResponse> {
    assertLap(lap);
    if (!driver) throw new RangeError("driver must be a non-empty code");
    const url = raceUrl(raceId, "strategy", { lap, driver });
    return sharedGet(url, (s) => getJson<StrategyResponse>(url, s), signal);
  },
  /** End-of-race Wrapped; the backend answers 409 before the final lap. */
  wrapped(raceId: string, lap: number, driver: string, signal?: AbortSignal): Promise<WrappedResponse> {
    assertLap(lap);
    if (!driver) throw new RangeError("driver must be a non-empty code");
    return getJson<WrappedResponse>(raceUrl(raceId, "wrapped", { lap, driver }), signal);
  },
};

/** Fetches the five per-lap responses in parallel; resolves only when all arrived. */
export async function fetchLapData(raceId: string, lap: number, signal?: AbortSignal): Promise<LapData> {
  const [state, laps, predictions, events, positions] = await Promise.all([
    api.state(raceId, lap, signal),
    api.laps(raceId, lap, signal),
    api.predictions(raceId, lap, signal),
    api.events(raceId, lap, signal),
    api.positions(raceId, lap, signal),
  ]);
  return { raceId, lap, state, laps, predictions, events, positions };
}
