import { useEffect, useRef, useState } from "react";
import { api, isAbortError } from "../api/client";

/** Prediction lap k-1 -> { driver code: predicted_next_lap_s } (the prediction for chart lap k). */
export type PredictionHistory = ReadonlyMap<number, Readonly<Record<string, number | null>>>;

const EMPTY: PredictionHistory = new Map();
/** Parallel /predictions requests while filling a gap (e.g. after a slider jump). */
const CONCURRENCY = 4;

interface Cache {
  /** Race and reload generation the cached predictions belong to. */
  scope: string | null;
  byLap: Map<number, Record<string, number | null>>;
}

/**
 * Per-race cache of `/predictions?lap=k` for k = 1..lap-1, the predictions the
 * lap-time chart draws for laps 2..lap. Only missing laps are requested, never
 * one at or above `lap`; moving the slider aborts requests still in flight.
 * A new `reload` value (e.g. after the served model changes) starts a fresh cache.
 */
export function usePredictionHistory(raceId: string | null, lap: number | null, reload = 0): PredictionHistory {
  const [cache, setCache] = useState<Cache>({ scope: null, byLap: new Map() });
  const cacheRef = useRef(cache);
  cacheRef.current = cache;
  const scope = raceId === null ? null : `${raceId}#${reload}`;

  useEffect(() => {
    if (raceId === null || scope === null || lap === null || lap < 2) return;
    const current = cacheRef.current;
    const known = current.scope === scope ? current.byLap : new Map<number, unknown>();
    const missing: number[] = [];
    for (let k = 1; k < lap; k++) if (!known.has(k)) missing.push(k);
    if (missing.length === 0) return;

    const controller = new AbortController();
    let next = 0;
    const worker = async () => {
      while (next < missing.length && !controller.signal.aborted) {
        const k = missing[next++];
        try {
          const response = await api.predictions(raceId, k, controller.signal);
          const values = Object.fromEntries(response.drivers.map((d) => [d.code, d.predicted_next_lap_s]));
          setCache((prev) => {
            const byLap = new Map(prev.scope === scope ? prev.byLap : []);
            byLap.set(k, values);
            return { scope, byLap };
          });
        } catch (error) {
          if (isAbortError(error)) return;
          // Leave the lap missing; the next lap change retries it.
        }
      }
    };
    for (let i = 0; i < CONCURRENCY; i++) void worker();
    return () => controller.abort();
  }, [raceId, scope, lap]);

  return cache.scope === scope ? cache.byLap : EMPTY;
}
