import { useEffect, useState } from "react";
import { fetchLapData, isAbortError } from "../api/client";
import type { LapData } from "../api/types";

export interface LapDataResult {
  /** The last lap whose five responses all arrived; may lag the requested lap. */
  data: LapData | null;
  error: Error | null;
  /** True while the requested race/lap is not yet the one in `data`. */
  pending: boolean;
}

/**
 * Fetches state, laps, predictions, events and positions for `lap` in parallel.
 * Changing the lap aborts the earlier lap's requests, so a fast slider move only
 * ever publishes the lap it stopped on; data is never mixed across laps.
 */
export function useLapData(raceId: string | null, lap: number, reloadToken = 0): LapDataResult {
  const [data, setData] = useState<LapData | null>(null);
  const [error, setError] = useState<{ key: string; error: Error } | null>(null);
  const key = `${raceId}@${lap}#${reloadToken}`;

  useEffect(() => {
    if (!raceId) return;
    const controller = new AbortController();
    fetchLapData(raceId, lap, controller.signal).then(
      (next) => {
        if (!controller.signal.aborted) setData(next);
      },
      (err: unknown) => {
        if (controller.signal.aborted || isAbortError(err)) return;
        controller.abort(); // stop the sibling requests of this failed lap
        setError({ key, error: err instanceof Error ? err : new Error(String(err)) });
      },
    );
    return () => controller.abort();
  }, [raceId, lap, key]);

  const current = error?.key === key ? error.error : null;
  const pending = raceId !== null && (data?.raceId !== raceId || data.lap !== lap) && current === null;
  return { data, error: current, pending };
}
