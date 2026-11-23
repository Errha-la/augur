import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { raceEvent } from "../test/builders";
import { IntelligencePanel } from "./IntelligencePanel";

// Vitest does not load CSS into modules, so read the stylesheet itself.
const css = readFileSync(join(process.cwd(), "src/index.css"), "utf8");

function clampOf(cls: string): { min: number; max: number } {
  const m = new RegExp(`\\.${cls}\\s*{[^}]*font-size:\\s*clamp\\((\\d+)px,[^,]+,\\s*(\\d+)px\\)`).exec(css);
  if (!m) throw new Error(`no clamp for .${cls}`);
  return { min: Number(m[1]), max: Number(m[2]) };
}

function noMaxWidth(el: HTMLElement) {
  for (let node: HTMLElement | null = el; node && node !== document.body; node = node.parentElement) {
    expect([...node.classList].filter((c) => c.startsWith("max-w"))).toEqual([]);
  }
}

describe("Text scales with the widget", () => {
  it("commentary, title and What/Why/Next use container-scaled sizes and no maximum line length", () => {
    const event = { ...raceEvent("e", 12, "pace_drop", ["VER"], 60), commentary: "VER lost 0.8 s a lap over the last three laps." };
    render(<IntelligencePanel raceId="r" events={[event]} commentaryModel="glm" focusCode={null} focusColor={null} />);
    const quote = screen.getByTestId("commentary-text");
    expect(quote).toHaveClass("cq-commentary", "w-full");
    expect(screen.getByTestId("event-title")).toHaveClass("cq-title");
    expect(screen.getByTestId("analysis")).toHaveClass("cq-body");
    for (const el of [quote, screen.getByTestId("event-title"), screen.getByTestId("analysis")]) {
      noMaxWidth(el);
      expect([...el.classList].filter((c) => /^text-(xs|sm|base|lg|xl)$/.test(c))).toEqual([]);
    }
  });

  it("widget bodies are size containers and the clamps match the spec ranges", () => {
    expect(css).toMatch(/\.widget-body\s*{\s*container-type:\s*inline-size;/);
    expect(clampOf("cq-commentary")).toEqual({ min: 13, max: 18 });
    expect(clampOf("cq-title")).toEqual({ min: 15, max: 22 });
    expect(clampOf("cq-body")).toEqual({ min: 12, max: 16 });
  });
});
