import { useEffect, useRef, useState } from "react";
import { isAbortError } from "../api/client";

export interface KeyedFetch<T> {
  /** Latest response and the key it was fetched for (kept while key is null). */
  value: T | null;
  valueKey: string | null;
  /** A request is in flight (possibly for an earlier key: see `loadingKey`). */
  loading: boolean;
  loadingKey: string | null;
  /** Latest failure and the key it belongs to. */
  error: Error | null;
  errorKey: string | null;
}

interface State<T> {
  value: T | null;
  valueKey: string | null;
  error: Error | null;
  errorKey: string | null;
  inflightKey: string | null;
}

/**
 * Fetches once per distinct non-null `key`; a new key aborts the previous
 * request. A null key starts nothing and lets an in-flight request finish, so
 * callers can skip requests (e.g. during playback) without losing a slow
 * response that is already on its way.
 */
export function useKeyedFetch<T>(key: string | null, fetcher: (signal: AbortSignal) => Promise<T>): KeyedFetch<T> {
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const inflight = useRef<{ key: string; controller: AbortController } | null>(null);
  const settledKey = useRef<string | null>(null);
  const [state, setState] = useState<State<T>>({
    value: null,
    valueKey: null,
    error: null,
    errorKey: null,
    inflightKey: null,
  });

  useEffect(() => {
    if (key === null || inflight.current?.key === key || settledKey.current === key) return;
    inflight.current?.controller.abort();
    const controller = new AbortController();
    const request = { key, controller };
    inflight.current = request;
    setState((s) => ({ ...s, inflightKey: key }));

    const finish = (patch: Partial<State<T>>) => {
      if (controller.signal.aborted) return;
      if (inflight.current === request) inflight.current = null;
      settledKey.current = key;
      setState((s) => ({ ...s, ...patch, inflightKey: s.inflightKey === key ? null : s.inflightKey }));
    };
    fetcherRef.current(controller.signal).then(
      (value) => finish({ value, valueKey: key, error: null, errorKey: null }),
      (err: unknown) => {
        if (isAbortError(err)) return;
        finish({ error: err instanceof Error ? err : new Error(String(err)), errorKey: key });
      },
    );
  }, [key]);

  useEffect(
    () => () => {
      inflight.current?.controller.abort();
      inflight.current = null;
      settledKey.current = null;
    },
    [],
  );

  return {
    value: state.value,
    valueKey: state.valueKey,
    loading: state.inflightKey !== null,
    loadingKey: state.inflightKey,
    error: state.error,
    errorKey: state.error ? state.errorKey : null,
  };
}
