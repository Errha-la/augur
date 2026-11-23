import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import { clearRequestCache } from "../api/requestCache";
import { GUIDE_KEY } from "../components/Guide";

// Tests start as a returning viewer; Guide.test.tsx removes this to test a first visit.
beforeEach(() => {
  localStorage.setItem(GUIDE_KEY, "done");
});

afterEach(() => {
  cleanup();
  clearRequestCache();
  localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
