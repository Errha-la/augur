import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RaceSummary } from "../api/types";
import { driver } from "../test/builders";
import { fixtures, type RequestCtx } from "../test/fakeBackend";
import { goToLap, renderApp, waitForShown } from "../test/renderApp";

const RACE_A = "2024-01-race-a";
const RACE_B = "2024-02-race-b";
const RACE_C = "2024-03-race-c";

const races: RaceSummary[] = [RACE_A, RACE_B, RACE_C].map((race_id, i) => ({
  race_id,
  year: 2024,
  round: i + 1,
  event_name: race_id,
  date: "2024-03-01",
  total_laps: 50,
}));

// Order at lap 1 per race; at later laps of race A, NOR leads.
const grids: Record<string, string[]> = {
  [RACE_A]: ["VER", "NOR", "LEC"],
  [RACE_B]: ["LEC", "PIA", "NOR"],
  [RACE_C]: ["HAM", "RUS", "ALO"],
};

function state({ raceId, lap }: RequestCtx) {
  const order = raceId === RACE_A && lap > 1 ? ["NOR", "VER", "LEC"] : grids[raceId];
  return {
    ...fixtures.state,
    race_id: raceId,
    lap,
    drivers: order.map((code, i) => driver(code, i + 1)),
  };
}

function focused() {
  return screen.getAllByTestId(/^row-/).filter((r) => r.dataset.focus === "true").map((r) => r.dataset.testid);
}

function selectRace(raceId: string) {
  fireEvent.change(screen.getByRole("combobox", { name: "Race" }), { target: { value: raceId } });
}

describe("Focus driver selection — focus changes", () => {
  it("race loads, P1 at lap 1 is VER → VER", async () => {
    await renderApp({ races, handlers: { state } });
    expect(focused()).toEqual(["row-VER"]);
  });

  it("stays on the lap 1 leader when the order changes later", async () => {
    await renderApp({ races, handlers: { state } });
    await goToLap(5);
    expect(focused()).toEqual(["row-VER"]);
  });

  it("viewer clicks the NOR row → NOR", async () => {
    await renderApp({ races, handlers: { state } });
    fireEvent.click(screen.getByTestId("row-NOR"));
    await waitFor(() => expect(focused()).toEqual(["row-NOR"]));
  });

  it("race changes, NOR is in the new race → NOR", async () => {
    await renderApp({ races, handlers: { state } });
    fireEvent.click(screen.getByTestId("row-NOR"));
    selectRace(RACE_B);
    await waitForShown(1, RACE_B);
    expect(focused()).toEqual(["row-NOR"]);
  });

  it("race changes, the focused code is not in the new race → P1 at lap 1 of the new race", async () => {
    await renderApp({ races, handlers: { state } });
    fireEvent.click(screen.getByTestId("row-NOR"));
    selectRace(RACE_C);
    await waitForShown(1, RACE_C);
    await waitFor(() => expect(focused()).toEqual(["row-HAM"]));
  });
});
