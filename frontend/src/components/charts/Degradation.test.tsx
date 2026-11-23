import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DegradationCompound, DegradationResponse } from "../../api/types";
import { DegradationView, fitLine, legendText } from "./Degradation";

function points(code: string, n: number) {
  return Array.from({ length: n }, (_, i) => ({ code, lap: 10 + i, tyre_age: 2 + i, fuel_corrected_s: 89 + i / 10 }));
}

const SOFT: DegradationCompound = {
  compound: "SOFT",
  fit: { slope_s_per_lap: 0.179, intercept_s: 89.602, n: 24 },
  points: [...points("MAG", 12), ...points("NOR", 12)],
};
const HARD: DegradationCompound = { compound: "HARD", fit: null, points: points("NOR", 3) };

describe("Degradation widget", () => {
  it("Legend entries: 'SOFT +0.179 s/lap (24)' with a fit and 'HARD (3)' without", () => {
    expect(legendText(SOFT)).toBe("SOFT +0.179 s/lap (24)");
    expect(legendText(HARD)).toBe("HARD (3)");
    const data: DegradationResponse = { race_id: "r", lap: 58, compounds: [SOFT, HARD] };
    render(<DegradationView data={data} focusCode="NOR" size={{ width: 500, height: 300 }} />);
    expect(screen.getByTestId("deg-legend-SOFT")).toHaveTextContent("SOFT +0.179 s/lap (24)");
    expect(screen.getByTestId("deg-legend-HARD")).toHaveTextContent("HARD (3)");
  });

  it("a negative slope keeps its sign", () => {
    expect(legendText({ ...SOFT, fit: { slope_s_per_lap: -0.02, intercept_s: 90, n: 5 } })).toBe("SOFT -0.020 s/lap (5)");
  });

  it("the fit line spans the compound's tyre ages; no line without a fit", () => {
    expect(fitLine(SOFT).map((p) => p.tyre_age)).toEqual([2, 13]);
    expect(fitLine(SOFT)[0].fuel_corrected_s).toBeCloseTo(89.602 + 0.179 * 2);
    expect(fitLine(HARD)).toEqual([]);
  });

  it("No laps yet: no compounds", () => {
    render(<DegradationView data={{ race_id: "r", lap: 1, compounds: [] }} focusCode={null} />);
    expect(screen.getByTestId("chart-message")).toHaveTextContent("No laps yet");
  });
});
