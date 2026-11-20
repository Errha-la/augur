import { useCallback, useEffect, useRef, useState } from "react";
import { api, isAbortError } from "../api/client";
import type { WrappedResponse } from "../api/types";

export type WrappedState =
  | { status: "closed" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "open"; data: WrappedResponse };

/** Opens the Wrapped for a race at its final lap and one driver; closes on race change. */
export function useWrapped(raceId: string | null) {
  const [state, setState] = useState<WrappedState>({ status: "closed" });
  const controller = useRef<AbortController | null>(null);

  const close = useCallback(() => {
    controller.current?.abort();
    controller.current = null;
    setState({ status: "closed" });
  }, []);

  const open = useCallback((race: string, finalLap: number, driver: string) => {
    controller.current?.abort();
    const c = new AbortController();
    controller.current = c;
    setState({ status: "loading" });
    api.wrapped(race, finalLap, driver, c.signal).then(
      (data) => {
        if (!c.signal.aborted) setState({ status: "open", data });
      },
      (err: unknown) => {
        if (c.signal.aborted || isAbortError(err)) return;
        setState({ status: "error", message: err instanceof Error ? err.message : String(err) });
      },
    );
  }, []);

  useEffect(() => close, [raceId, close]);

  return { state, open, close };
}
