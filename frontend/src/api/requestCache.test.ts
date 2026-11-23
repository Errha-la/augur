import { afterEach, describe, expect, it, vi } from "vitest";
import { clearRequestCache, requestCacheSize, sharedGet } from "./requestCache";

afterEach(() => clearRequestCache());

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("sharedGet", () => {
  it("sends one request for concurrent callers of the same URL and keeps the response", async () => {
    const d = deferred<number>();
    const load = vi.fn(() => d.promise);
    const a = sharedGet("/u", load);
    const b = sharedGet("/u", load);
    d.resolve(7);
    await expect(a).resolves.toBe(7);
    await expect(b).resolves.toBe(7);
    await expect(sharedGet("/u", load)).resolves.toBe(7);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("aborts the request only when every caller aborted", async () => {
    let seen: AbortSignal | undefined;
    const load = vi.fn((signal: AbortSignal) => {
      seen = signal;
      return new Promise<number>(() => {});
    });
    const c1 = new AbortController();
    const c2 = new AbortController();
    const a = sharedGet("/u", load, c1.signal);
    const b = sharedGet("/u", load, c2.signal);
    c1.abort();
    await expect(a).rejects.toMatchObject({ name: "AbortError" });
    expect(seen?.aborted).toBe(false);
    c2.abort();
    await expect(b).rejects.toMatchObject({ name: "AbortError" });
    expect(seen?.aborted).toBe(true);
    expect(requestCacheSize()).toBe(0);
  });

  it("does not keep failures", async () => {
    const load = vi.fn().mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce(1);
    await expect(sharedGet("/u", load)).rejects.toThrow("boom");
    await expect(sharedGet("/u", load)).resolves.toBe(1);
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("clearRequestCache forgets kept responses", async () => {
    const load = vi.fn().mockResolvedValue(1);
    await sharedGet("/u", load);
    clearRequestCache();
    await sharedGet("/u", load);
    expect(load).toHaveBeenCalledTimes(2);
  });
});
