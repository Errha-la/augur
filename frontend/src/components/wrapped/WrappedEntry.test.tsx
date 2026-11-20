import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ABU_DHABI } from "../../test/fakeBackend";
import { goToLap, renderApp } from "../../test/renderApp";

function wrappedButton() {
  return screen.getByRole("button", { name: /^Wrapped/ });
}

describe("Wrapped entry point", () => {
  // Scenario: Unlock at the final lap
  it("changes from locked to enabled when the replay moves from lap 57 to lap 58", async () => {
    await renderApp();
    expect(wrappedButton()).toBeDisabled();

    await goToLap(57);
    expect(wrappedButton()).toBeDisabled();
    expect(wrappedButton()).toHaveAccessibleName("Wrapped (unlocks at the final lap)");
    expect(screen.getByTestId("wrapped-lock")).toBeInTheDocument();

    await goToLap(58);
    expect(wrappedButton()).toBeEnabled();
    expect(wrappedButton()).toHaveAccessibleName("Wrapped");
    expect(screen.queryByTestId("wrapped-lock")).not.toBeInTheDocument();
  });

  it("requests /wrapped for the race, the final lap and the focus driver, then opens the overlay", async () => {
    const { backend } = await renderApp();
    await goToLap(58);
    fireEvent.click(screen.getByTestId("row-HAM"));
    fireEvent.click(wrappedButton());

    await waitFor(() => expect(screen.getByTestId("wrapped-story")).toBeInTheDocument());
    const requests = backend.of("wrapped");
    expect(requests.map((r) => [r.raceId, r.lap, r.driver])).toEqual([[ABU_DHABI, 58, "HAM"]]);
    expect(screen.getByRole("dialog", { name: "Race Wrapped" })).toBeInTheDocument();
  });

  it("shows the backend's refusal and closes with Esc", async () => {
    await renderApp({ handlers: { wrapped: () => new Response('{"detail":"race not analyzed"}', { status: 409 }) } });
    await goToLap(58);
    fireEvent.click(wrappedButton());
    expect(await screen.findByText(/Wrapped unavailable/)).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByTestId("wrapped-overlay")).not.toBeInTheDocument());
  });
});
