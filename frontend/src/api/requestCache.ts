// Shared GETs for widgets: several widgets asking for the same URL (e.g. two
// driver widgets following the same driver at the same lap) send one request.
// A response is kept until the race changes or the model is reloaded
// (`clearRequestCache`); failures are never kept. The network request is
// aborted only when every caller waiting for it has aborted.

interface Entry {
  promise: Promise<unknown>;
  controller: AbortController;
  waiters: number;
  settled: boolean;
}

/** Bound on kept responses (a 58-lap race with two pinned drivers stays well under it). */
export const MAX_ENTRIES = 300;

const entries = new Map<string, Entry>();

function abortError(): DOMException {
  return new DOMException("The operation was aborted.", "AbortError");
}

function evict(): void {
  for (const [url, entry] of entries) {
    if (entries.size <= MAX_ENTRIES) return;
    if (entry.settled) entries.delete(url);
  }
}

export function sharedGet<T>(url: string, load: (signal: AbortSignal) => Promise<T>, signal?: AbortSignal): Promise<T> {
  if (signal?.aborted) return Promise.reject(abortError());
  let entry = entries.get(url);
  if (!entry) {
    const controller = new AbortController();
    const created: Entry = { controller, waiters: 0, settled: false, promise: Promise.resolve() };
    created.promise = load(controller.signal).then(
      (value) => {
        created.settled = true;
        return value;
      },
      (err: unknown) => {
        if (entries.get(url) === created) entries.delete(url);
        throw err;
      },
    );
    entries.set(url, created);
    evict();
    entry = created;
  }
  if (entry.settled) return entry.promise as Promise<T>;

  const shared = entry;
  shared.waiters++;
  return new Promise<T>((resolve, reject) => {
    let done = false;
    const leave = () => {
      done = true;
      shared.waiters--;
      signal?.removeEventListener("abort", onAbort);
    };
    const onAbort = () => {
      if (done) return;
      leave();
      if (shared.waiters === 0 && !shared.settled) {
        shared.controller.abort();
        if (entries.get(url) === shared) entries.delete(url);
      }
      reject(abortError());
    };
    signal?.addEventListener("abort", onAbort, { once: true });
    shared.promise.then(
      (value) => {
        if (done) return;
        leave();
        resolve(value as T);
      },
      (err: unknown) => {
        if (done) return;
        leave();
        reject(err);
      },
    );
  });
}

export function clearRequestCache(): void {
  entries.clear();
}

export function requestCacheSize(): number {
  return entries.size;
}
