import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, vi } from "vitest";
import App from "../App";
import type { Board } from "../canvas/board";
import type { BoardsState } from "../canvas/store";
import { fakeBackend, type FakeBackendOptions } from "./fakeBackend";

/**
 * The fixed layout before boards, as one board: every panel once, events
 * unfiltered, driver widgets following the focus driver. App tests use it so
 * their assertions see all panels.
 */
export const CLASSIC_BOARD: Board = {
  id: "classic",
  name: "Classic",
  presetId: null,
  widgets: [
    { id: "timing-1", type: "timing", x: 0, y: 0, w: 5, h: 14, settings: {} },
    { id: "events-1", type: "events", x: 5, y: 0, w: 7, h: 6, settings: {} },
    { id: "driver-1", type: "driver", x: 5, y: 6, w: 4, h: 6, settings: {} },
    { id: "lapchart-1", type: "lapchart", x: 9, y: 6, w: 3, h: 6, settings: {} },
    { id: "timeline-1", type: "timeline", x: 5, y: 12, w: 7, h: 2, settings: {} },
  ],
};

/** Board state with `board` as the only custom board, active. */
export function boardsWith(board: Board): BoardsState {
  return { activeBoardId: board.id, presetEdits: {}, customBoards: [board] };
}

/** Renders the app against a fake backend and waits until lap 1 of the first race is shown. */
export async function renderApp(options: FakeBackendOptions = {}, { waitForLap = true } = {}) {
  const backend = fakeBackend(options);
  const view = render(<App initialBoards={boardsWith(CLASSIC_BOARD)} />);
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
