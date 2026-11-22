import { render, screen } from "@testing-library/react";
import { forwardRef, type ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { driver } from "../test/builders";
import { ROW_TRANSITION, TimingList } from "./TimingList";

// Record the motion props each row receives instead of measuring layout in jsdom.
vi.mock("motion/react", () => ({
  MotionConfig: ({ children }: { children: React.ReactNode }) => children,
  motion: {
    tr: forwardRef<HTMLTableRowElement, ComponentProps<"tr"> & { layout?: unknown; transition?: unknown }>(
      ({ layout, transition, ...rest }, ref) => (
        <tr ref={ref} data-layout={String(layout)} data-transition={JSON.stringify(transition)} {...rest} />
      ),
    ),
  },
}));

function list(order: string[]) {
  return (
    <TimingList
      lap={20}
      drivers={order.map((code, i) => driver(code, i + 1))}
      laps={[]}
      predictions={[]}
      positions={[]}
      focusCode={null}
      onFocus={() => {}}
    />
  );
}

describe("Timing list — Animated position changes", () => {
  // specs/timing-animation — Scenario: Two drivers swap
  it("animates only the two rows that swap P3 and P4", () => {
    const { rerender } = render(list(["VER", "NOR", "LEC", "PIA", "HAM"]));
    expect(screen.queryAllByTestId(/^row-/).filter((r) => r.dataset.moved)).toEqual([]);

    rerender(list(["VER", "NOR", "PIA", "LEC", "HAM"]));
    const moved = screen.queryAllByTestId(/^row-/).filter((r) => r.dataset.moved).map((r) => r.dataset.testid);
    expect(moved).toEqual(["row-PIA", "row-LEC"]);
  });

  it("gives every row a position layout animation with the design's ease and 0.75 s", () => {
    render(list(["VER", "NOR"]));
    expect(ROW_TRANSITION).toEqual({ duration: 0.75, ease: [0.2, 1, 0.2, 1] });
    for (const row of screen.queryAllByTestId(/^row-/)) {
      expect(row.dataset.layout).toBe("position");
      expect(JSON.parse(row.dataset.transition!)).toEqual(ROW_TRANSITION);
    }
  });

  it("clears the moved mark when the next lap keeps the order", () => {
    const { rerender } = render(list(["VER", "NOR", "LEC"]));
    rerender(list(["NOR", "VER", "LEC"]));
    rerender(list(["NOR", "VER", "LEC"]));
    expect(screen.queryAllByTestId(/^row-/).filter((r) => r.dataset.moved)).toEqual([]);
  });
});
