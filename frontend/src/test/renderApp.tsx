import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, vi } from "vitest";
import App from "../App";
import { fakeBackend, type FakeBackendOptions } from "./fakeBackend";

/** Renders the app against a fake backend and waits until lap 1 of the first race is shown. */
export async function renderApp(options: FakeBackendOptions = {}, { waitForLap = true } = {}) {
  const backend = fakeBackend(options);
  const view = render(<App />);
  if (waitForLap) await waitForShown(1);
  return { backend, ...view };
}

export function layout() {
  return screen.getByTestId("layout");
}

export async function waitForShown(lap: number, raceId?: string) {
  await waitFor(() => {
    expect(layout()).toHaveAttribute("data-lap", String(lap));
    if (raceId) expect(layout()).toHaveAttribute("data-race", raceId);
  });
}

export function lapCount() {
  return screen.getByTestId("lap-count").textContent;
}

export async function goToLap(lap: number) {
  fireEvent.change(screen.getByRole("slider", { name: "Lap" }), { target: { value: String(lap) } });
  await waitForShown(lap);
}

export async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
