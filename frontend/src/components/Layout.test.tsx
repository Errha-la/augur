import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Layout } from "./Layout";

describe("Layout", () => {
  it("renders the empty timing-screen layout on the zinc-950 background", () => {
    render(<Layout />);
    expect(screen.getByTestId("layout")).toHaveClass("bg-zinc-950");
    for (const id of ["status-bar", "timing", "intelligence", "focus", "chart", "timeline"]) {
      expect(screen.getByTestId(id)).toBeInTheDocument();
    }
  });
});
