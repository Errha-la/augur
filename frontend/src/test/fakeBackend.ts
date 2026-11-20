import { vi } from "vitest";
import type {
  EventsResponse,
  LapRow,
  PositionsHistoryResponse,
  PositionsResponse,
  PredictionsResponse,
  RaceState,
  RaceSummary,
  StrategyResponse,
} from "../api/types";
import { wrappedResponse } from "./builders";
import eventsFixture from "./fixtures/events.json";
import lapsFixture from "./fixtures/laps.json";
import positionsFixture from "./fixtures/positions.json";
import historyFixture from "./fixtures/positions_history.json";
import predictionsFixture from "./fixtures/predictions.json";
import racesFixture from "./fixtures/races.json";
import stateFixture from "./fixtures/state.json";
import strategyFixture from "./fixtures/strategy.json";

// Fixtures are real backend responses for 2024 Abu Dhabi at lap 15. The fake
// backend re-labels them with the requested lap and drops rows after it, so
// tests see cutoff-safe data like the real API returns.

export const fixtures = {
  races: racesFixture as RaceSummary[],
  state: stateFixture as RaceState,
  laps: lapsFixture as LapRow[],
  predictions: predictionsFixture as PredictionsResponse,
  events: eventsFixture as EventsResponse,
  positions: positionsFixture as PositionsResponse,
  history: historyFixture as PositionsHistoryResponse,
  strategy: strategyFixture as StrategyResponse,
};

export const ABU_DHABI = "2024-24-abu-dhabi-grand-prix";
export const BAHRAIN = "2024-01-bahrain-grand-prix";

export type Endpoint =
  | "state"
  | "laps"
  | "predictions"
  | "events"
  | "positions"
  | "positions/history"
  | "strategy"
  | "wrapped";

export interface RequestCtx {
  raceId: string;
  lap: number;
  driver: string | null;
}

export interface RecordedRequest extends RequestCtx {
  endpoint: Endpoint | "races";
  url: string;
  signal: AbortSignal | undefined;
}

type Handler = (ctx: RequestCtx) => unknown;

export interface FakeBackendOptions {
  /** Race list, or "down" to make /api/races fail like an unreachable backend. */
  races?: RaceSummary[] | "down";
  handlers?: Partial<Record<Endpoint, Handler>>;
  /** Hold every lap response until `release` is called. */
  manual?: boolean;
}

const defaultHandlers: Record<Endpoint, Handler> = {
  state: ({ raceId, lap }) => ({ ...fixtures.state, race_id: raceId, lap }),
  laps: ({ lap }) => fixtures.laps.filter((r) => r.lap <= lap),
  predictions: ({ raceId, lap }) => ({ ...fixtures.predictions, race_id: raceId, lap }),
  events: ({ raceId, lap }) => ({
    ...fixtures.events,
    race_id: raceId,
    lap,
    events: fixtures.events.events.filter((e) => e.lap <= lap),
  }),
  positions: ({ raceId, lap }) => ({ ...fixtures.positions, race_id: raceId, lap }),
  "positions/history": ({ raceId, lap }) => ({
    ...fixtures.history,
    race_id: raceId,
    laps: fixtures.history.laps.filter((l) => l.lap <= lap),
  }),
  strategy: ({ raceId, lap, driver }) => ({ ...fixtures.strategy, race_id: raceId, lap, driver }),
  wrapped: ({ raceId, driver }) => wrappedResponse({ race_id: raceId }, { code: driver ?? "NOR" }),
};

interface Held {
  request: RecordedRequest;
  resolve: () => void;
}

function abortError(): DOMException {
  return new DOMException("The operation was aborted.", "AbortError");
}

export function fakeBackend(options: FakeBackendOptions = {}) {
  let races = options.races ?? fixtures.races;
  const handlers = { ...defaultHandlers, ...options.handlers };
  const requests: RecordedRequest[] = [];
  const held: Held[] = [];

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = String(input);
    const parsed = new URL(url, "http://localhost");
    const signal = init?.signal ?? undefined;
    if (signal?.aborted) throw abortError();

    if (parsed.pathname === "/api/races") {
      requests.push({ endpoint: "races", url, signal, raceId: "", lap: 0, driver: null });
      if (races === "down") throw new TypeError("Failed to fetch");
      return Response.json(races);
    }

    const match = /^\/api\/races\/([^/]+)\/(.+)$/.exec(parsed.pathname);
    if (!match) return new Response("not found", { status: 404 });
    const endpoint = match[2] as Endpoint;
    const ctx: RequestCtx = {
      raceId: decodeURIComponent(match[1]),
      lap: Number(parsed.searchParams.get("lap")),
      driver: parsed.searchParams.get("driver"),
    };
    const request: RecordedRequest = { ...ctx, endpoint, url, signal };
    requests.push(request);
    const handler = handlers[endpoint];
    if (!handler) return new Response("not found", { status: 404 });

    if (options.manual) {
      await new Promise<void>((resolve, reject) => {
        held.push({ request, resolve });
        signal?.addEventListener("abort", () => reject(abortError()), { once: true });
      });
    }
    if (signal?.aborted) throw abortError();
    const body = handler(ctx);
    if (body instanceof Response) return body;
    return Response.json(body);
  });

  vi.stubGlobal("fetch", fetchMock);

  return {
    fetch: fetchMock,
    requests,
    /** Requests of one endpoint, in order. */
    of(endpoint: Endpoint | "races") {
      return requests.filter((r) => r.endpoint === endpoint);
    },
    /** Releases held responses (all, or those matching `filter`). */
    release(filter: (r: RecordedRequest) => boolean = () => true) {
      for (let i = held.length - 1; i >= 0; i--) {
        if (filter(held[i].request)) held.splice(i, 1)[0].resolve();
      }
    },
    setRaces(next: RaceSummary[] | "down") {
      races = next;
    },
  };
}
