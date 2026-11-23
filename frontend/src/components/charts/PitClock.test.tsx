import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RejoinResponse, RejoinSlot } from "../../api/types";
import { clockAngle, lappedLabel, PitClockView, rejoinText } from "./PitClock";

function rejoin(slot: RejoinSlot | null): RejoinResponse {
  return {
    race_id: "r",
    lap: 20,
    driver: "NOR",
    pit_loss_s: 21.5,
    lap_length_s: 88,
    cars: [
      { code: "VER", position: 1, gap_to_leader_s: 0, laps_behind_leader: 0 },
      { code: "NOR", position: 2, gap_to_leader_s: 4, laps_behind_leader: 0 },
      { code: "SAR", position: 20, gap_to_leader_s: 110, laps_behind_leader: 1 },
    ],
    rejoin: slot,
  };
}

const SLOT: RejoinSlot = { position: 7, gap_to_leader_s: 25.5, ahead: "RUS", ahead_gap_s: 1.1, behind: "HAM", behind_gap_s: 0.6 };

describe("Pit clock widget", () => {
  it("Rejoin text: P7, 1.1 s behind RUS, 0.6 s ahead of HAM, and the pit loss", () => {
    expect(rejoinText(SLOT)).toBe("Pit now: rejoin P7, 1.1 s behind RUS, 0.6 s ahead of HAM");
    render(<PitClockView data={rejoin(SLOT)} code="NOR" teamColors={{}} />);
    expect(screen.getByTestId("rejoin-text")).toHaveTextContent("Pit now: rejoin P7, 1.1 s behind RUS, 0.6 s ahead of HAM");
    expect(screen.getByText("Pit loss 21.5 s")).toBeInTheDocument();
    expect(screen.getByText("Snapshot: assumes no other car pits this lap")).toBeInTheDocument();
  });

  it("Leader rejoins in front: P1, 2.0 s ahead of SAI", () => {
    expect(rejoinText({ position: 1, gap_to_leader_s: 21.5, ahead: null, ahead_gap_s: null, behind: "SAI", behind_gap_s: 2 })).toBe(
      "Pit now: rejoin P1, 2.0 s ahead of SAI",
    );
  });

  it.each([
    [88, 0, 0, 0, null],
    [88, 22, 0, 90, null],
    [88, 110, 1, 90, "+1L"],
  ])("Car positions on the clock: lap %s, gap %s, %s laps down -> %s°, %s", (lapLength, gap, down, angle, label) => {
    expect(clockAngle(gap, lapLength)).toBeCloseTo(angle);
    expect(lappedLabel(down)).toBe(label);
  });

  it("rings the widget's driver and labels lapped cars", () => {
    render(<PitClockView data={rejoin(SLOT)} code="NOR" teamColors={{}} />);
    expect(screen.getByTestId("clock-car-NOR")).toHaveAttribute("data-own", "true");
    expect(screen.getByTestId("clock-car-VER")).not.toHaveAttribute("data-own");
    expect(screen.getByTestId("clock-car-SAR")).toHaveTextContent("SAR +1L");
  });

  it("shows '<code> has no gap yet' when rejoin is null", () => {
    render(<PitClockView data={rejoin(null)} code="NOR" teamColors={{}} />);
    expect(screen.getByTestId("chart-message")).toHaveTextContent("NOR has no gap yet");
  });
});
