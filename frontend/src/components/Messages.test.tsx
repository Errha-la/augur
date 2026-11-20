import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ABU_DHABI, fixtures } from "../test/fakeBackend";
import { lapCount, renderApp, waitForShown } from "../test/renderApp";

describe("Backend status messages", () => {
  it("shows the unreachable banner with Retry when /api/races fails", async () => {
    await renderApp({ races: "down" }, { waitForLap: false });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Backend not reachable at /api. Start it with: uvicorn augur.api:app");
    expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  // Scenario: Backend down then retried
  it("removes the banner and loads the first race at lap 1 after Retry", async () => {
    const { backend } = await renderApp({ races: "down" }, { waitForLap: false });
    const retry = await screen.findByRole("button", { name: "Retry" });
    backend.setRaces(fixtures.races);
    fireEvent.click(retry);

    await waitForShown(1, ABU_DHABI);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(lapCount()).toBe("LAP 1/58");
  });

  it("shows the no-races message when the race list is empty", async () => {
    await renderApp({ races: [] }, { waitForLap: false });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No races ingested. Run: python -m augur.ingest --year 2024 --rounds 1 24",
    );
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("shows the not-analyzed message in the intelligence panel only", async () => {
    await renderApp({
      handlers: {
        events: ({ raceId, lap }) => ({ race_id: raceId, lap, model: "lightgbm", analyzed: false, events: [] }),
      },
    });
    const panel = screen.getByTestId("intelligence");
    expect(within(panel).getByRole("status")).toHaveTextContent(
      `Race not analyzed. Run: python -m augur.analyze --race ${ABU_DHABI}`,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a retryable banner when a lap request fails", async () => {
    let fail = true;
    await renderApp(
      { handlers: { state: (ctx) => (fail ? new Response("down", { status: 502 }) : { ...fixtures.state, ...ctx }) } },
      { waitForLap: false },
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not load lap 1");
    fail = false;
    fireEvent.click(within(alert).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    await waitForShown(1);
  });
});
