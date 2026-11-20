import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ABU_DHABI, BAHRAIN } from "../test/fakeBackend";
import { advance, goToLap, lapCount, layout, renderApp, waitForShown } from "../test/renderApp";
import { TrackStatusPill } from "./StatusBar";

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

function playButton() {
  return screen.getByRole("button", { name: /^(Play|Pause)$/ });
}

describe("Race selection", () => {
  it("loads the first race at lap 1 and lists races by name and year", async () => {
    await renderApp();
    expect(layout()).toHaveAttribute("data-race", ABU_DHABI);
    expect(lapCount()).toBe("LAP 1/58");
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(["Abu Dhabi Grand Prix 2024", "Bahrain Grand Prix 2024"]);
  });

  // Scenario: Switch race
  it("resets to lap 1 and stops playback when another race is selected at lap 30", async () => {
    const { backend } = await renderApp();
    await goToLap(30);
    fireEvent.click(playButton());
    expect(playButton()).toHaveAccessibleName("Pause");

    fireEvent.change(screen.getByRole("combobox", { name: "Race" }), { target: { value: BAHRAIN } });

    await waitForShown(1, BAHRAIN);
    expect(lapCount()).toBe("LAP 1/57");
    expect(playButton()).toHaveAccessibleName("Play");
    const bahrain = backend.requests.filter((r) => r.raceId === BAHRAIN);
    expect(new Set(bahrain.map((r) => r.lap))).toEqual(new Set([1]));
  });
});

describe("Lap navigation and playback — navigation cases", () => {
  it("lap 1, previous → 1", async () => {
    await renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Previous lap" }));
    fireEvent.keyDown(window, { key: "ArrowLeft" });
    await advance(50);
    expect(lapCount()).toBe("LAP 1/58");
  });

  it("lap 1, Right arrow → 2", async () => {
    await renderApp();
    fireEvent.keyDown(window, { key: "ArrowRight" });
    await waitForShown(2);
    expect(lapCount()).toBe("LAP 2/58");
  });

  it("57 of 57, next → 57", async () => {
    await renderApp();
    fireEvent.change(screen.getByRole("combobox", { name: "Race" }), { target: { value: BAHRAIN } });
    await waitForShown(1, BAHRAIN);
    await goToLap(57);
    fireEvent.click(screen.getByRole("button", { name: "Next lap" }));
    fireEvent.keyDown(window, { key: "ArrowRight" });
    await advance(50);
    expect(lapCount()).toBe("LAP 57/57");
  });

  it("56 of 57, playing, one tick → 57 and playback stops", async () => {
    await renderApp();
    fireEvent.change(screen.getByRole("combobox", { name: "Race" }), { target: { value: BAHRAIN } });
    await waitForShown(1, BAHRAIN);
    await goToLap(56);
    fireEvent.keyDown(window, { key: " " });
    expect(playButton()).toHaveAccessibleName("Pause");

    await advance(1000);
    await waitForShown(57);
    expect(playButton()).toHaveAccessibleName("Play");
    await advance(3000);
    expect(lapCount()).toBe("LAP 57/57");
  });

  it("advances one lap per 250 ms at 4× and waits for each lap to render", async () => {
    const { backend } = await renderApp();
    fireEvent.click(screen.getByRole("button", { name: "4×" }));
    fireEvent.click(playButton());
    await advance(250);
    await waitForShown(2);
    await advance(250);
    await waitForShown(3);
    fireEvent.keyDown(window, { key: " " });
    await advance(1000);
    expect(lapCount()).toBe("LAP 3/58");
    expect(Math.max(...backend.requests.map((r) => r.lap))).toBe(3);
  });
});

describe("TrackStatusPill", () => {
  it.each([
    ["1", "bg-emerald-500", "GREEN"],
    ["4", "bg-flag-yellow", "SAFETY CAR"],
    ["5", "bg-flag-red", "RED FLAG"],
  ])("status %s is coloured %s", (status, className, label) => {
    render(<TrackStatusPill status={status} />);
    const pill = screen.getByTestId("track-status");
    expect(pill).toHaveClass(className);
    expect(pill).toHaveTextContent(label);
  });
});
