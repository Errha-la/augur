import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearRequestCache } from "../../api/requestCache";
import type { DegradationResponse, LinkChart, NumberLink } from "../../api/types";
import { ABU_DHABI, type Endpoint, fakeBackend } from "../../test/fakeBackend";
import { ChartPopover, driverDegradation, fitPoints, POPOVER_FAILED, POPOVER_LOADING, popoverTitle } from "./ChartPopover";

let backend: ReturnType<typeof fakeBackend>;

beforeEach(() => {
  backend = fakeBackend();
});

afterEach(() => {
  clearRequestCache();
  vi.unstubAllGlobals();
});

const EVENT_LAP = 20;

function link(chart: LinkChart, drivers: string[], field = "gap_s"): NumberLink {
  return { start: 0, end: 3, field, chart, drivers };
}

function popover(l: NumberLink, onClose = vi.fn(), evidence: Record<string, unknown> = {}) {
  return render(
    <ChartPopover
      raceId={ABU_DHABI}
      lap={EVENT_LAP}
      link={l}
      evidence={evidence}
      totalLaps={58}
      teamColors={{ NOR: "#FF8000", PIA: "#FF8000" }}
      anchor={null}
      onClose={onClose}
    />,
  );
}

async function loaded() {
  const dialog = await screen.findByRole("dialog");
  await vi.waitFor(() => expect(dialog).not.toHaveTextContent(POPOVER_LOADING));
  return dialog;
}

function lapsOf(endpoint: Endpoint) {
  return backend.of(endpoint).map((r) => r.lap);
}

describe("ChartPopover: one chart per kind at the event lap", () => {
  it("trace: title, one /trace?lap=E request, only the link's drivers", async () => {
    const { container } = popover(link("trace", ["NOR", "PIA"]));
    expect(screen.getByRole("dialog", { name: "Race trace · NOR PIA · lap 20" })).toBeInTheDocument();
    await loaded();
    expect(lapsOf("trace")).toEqual([EVENT_LAP]);
    expect(container.ownerDocument.querySelectorAll("path.recharts-line-curve")).toHaveLength(2);
  });

  it("stints: /stints?lap=E and only the link's drivers' rows", async () => {
    popover(link("stints", ["PIA"], "ahead_tyre_life"));
    await loaded();
    expect(lapsOf("stints")).toEqual([EVENT_LAP]);
    expect(screen.getByTestId("stints-PIA")).toBeInTheDocument();
    expect(screen.queryByTestId("stints-NOR")).toBeNull();
  });

  it("degradation: /degradation?lap=E, only the driver's points, evidence value in the caption", async () => {
    popover(link("degradation", ["SAI"], "deg_s_per_lap"), vi.fn(), { deg_s_per_lap: 0.084 });
    const dialog = await loaded();
    expect(lapsOf("degradation")).toEqual([EVENT_LAP]);
    expect(screen.getByTestId("popover-caption")).toHaveTextContent("deg_s_per_lap 0.084");
    const dots = [...dialog.querySelectorAll("circle")].filter((c) => c.getAttribute("r") !== null);
    expect(dots.length).toBe(EVENT_LAP - 1);
    expect(dots.every((c) => c.getAttribute("data-focus") === "true")).toBe(true);
  });

  it("laptimes: /laps?lap=E and /state?lap=E, the lap-time chart focused on the driver", async () => {
    popover(link("laptimes", ["NOR"], "lap_time_s"));
    await loaded();
    expect(lapsOf("laps")).toEqual([EVENT_LAP]);
    expect(lapsOf("state")).toEqual([EVENT_LAP]);
    expect(screen.getByTestId("chart-legend")).toHaveTextContent("Neighbours at lap 20");
    expect(screen.getByTestId("chart-legend")).toHaveTextContent("NOR");
  });

  it("pitwindow: /pit-window?lap=E&driver=D", async () => {
    popover(link("pitwindow", ["NOR"], "strategy.win_probability"));
    await loaded();
    expect(backend.of("pit-window").map((r) => [r.lap, r.driver])).toEqual([[EVENT_LAP, "NOR"]]);
    expect(screen.getByTestId("best-pit-lap")).toHaveTextContent("Best: lap 22");
  });

  it("positions: /positions/history?lap=E and the driver's fan", async () => {
    popover(link("positions", ["NOR"], "to_position"));
    await loaded();
    expect(lapsOf("positions/history")).toEqual([EVENT_LAP]);
    expect(screen.getByTestId("chart-caption")).toHaveTextContent("NOR: expected position");
  });
});

describe("ChartPopover states", () => {
  it("shows Loading... until the response arrives", async () => {
    clearRequestCache();
    vi.unstubAllGlobals();
    backend = fakeBackend({ manual: true });
    popover(link("trace", ["NOR", "PIA"]));
    expect(screen.getByRole("dialog")).toHaveTextContent(POPOVER_LOADING);
    await vi.waitFor(() => expect(backend.of("trace")).toHaveLength(1));
    backend.release();
    await loaded();
    expect(screen.getByRole("dialog")).toHaveTextContent("Reference pace");
  });

  it("shows 'Could not load chart' on failure", async () => {
    vi.unstubAllGlobals();
    backend = fakeBackend({ handlers: { stints: () => new Response("boom", { status: 500 }) } });
    popover(link("stints", ["NOR"]));
    expect(await screen.findByText(POPOVER_FAILED)).toBeInTheDocument();
  });

  it("closes on Escape and on a click outside, not on a click inside", async () => {
    const onClose = vi.fn();
    popover(link("trace", ["NOR", "PIA"]), onClose);
    const dialog = await loaded();
    fireEvent.mouseDown(dialog);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.mouseDown(document.body);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});

describe("Popover helpers", () => {
  it("title joins chart title, drivers and the event lap", () => {
    expect(popoverTitle(link("trace", ["NOR", "PIA"]), 20)).toBe("Race trace · NOR PIA · lap 20");
    expect(popoverTitle(link("positions", ["VER"]), 7)).toBe("Position fan · VER · lap 7");
  });

  it("driver degradation keeps the driver's points and refits them", () => {
    const pts = (code: string, base: number) =>
      [2, 3, 4].map((age) => ({ code, lap: age, tyre_age: age, fuel_corrected_s: base + 0.1 * age }));
    const data: DegradationResponse = {
      race_id: "r",
      lap: 5,
      compounds: [
        { compound: "MEDIUM", fit: { slope_s_per_lap: 9, intercept_s: 0, n: 6 }, points: [...pts("NOR", 90), ...pts("PIA", 80)] },
        { compound: "HARD", fit: null, points: pts("PIA", 70) },
      ],
    };
    const only = driverDegradation(data, "NOR");
    expect(only.compounds.map((c) => c.compound)).toEqual(["MEDIUM"]);
    expect(only.compounds[0].points.every((p) => p.code === "NOR")).toBe(true);
    expect(only.compounds[0].fit?.slope_s_per_lap).toBeCloseTo(0.1);
    expect(only.compounds[0].fit?.intercept_s).toBeCloseTo(90);
    expect(fitPoints(pts("NOR", 90).slice(0, 1))).toBeNull();
  });
});
