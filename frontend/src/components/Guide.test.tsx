import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { fakeBackend } from "../test/fakeBackend";
import { waitForShown } from "../test/renderApp";
import { GUIDE_KEY, GUIDE_STEPS } from "./Guide";

beforeEach(() => localStorage.removeItem(GUIDE_KEY));

async function open() {
  fakeBackend();
  const view = render(<App />);
  await waitForShown(1);
  return view;
}

function guide() {
  return screen.getByRole("dialog");
}

function step() {
  return within(guide()).getByText(/^Step \d of 4$/).textContent;
}

function button(name: string) {
  return within(guide()).getByRole("button", { name });
}

describe("First-visit guide", () => {
  it("First visit: step 1 of 4 opens; after Skip it closes and does not open on reload", async () => {
    const view = await open();
    expect(step()).toBe("Step 1 of 4");
    expect(guide()).toHaveAccessibleName(GUIDE_STEPS[0].title);
    expect(within(guide()).queryByRole("button", { name: "Back" })).not.toBeInTheDocument();
    fireEvent.click(button("Skip"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(localStorage.getItem(GUIDE_KEY)).not.toBeNull();
    view.unmount();
    await open();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("each step is anchored to the element it explains", async () => {
    await open();
    const anchors: string[] = [];
    for (let i = 0; i < 4; i++) {
      // jsdom has no layout, so anchors are found but have no size: check the target exists.
      anchors.push(GUIDE_STEPS[i].anchor);
      expect(document.querySelector(`[data-guide="${GUIDE_STEPS[i].anchor}"]`)).not.toBeNull();
      if (i < 3) fireEvent.click(button("Next"));
    }
    expect(anchors).toEqual(["title-bar", "resize", "add-widget", "board-menu"]);
  });

  it("anchors the card next to its element when the element has a size", async () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(100, 60, 200, 30));
    await open();
    expect(guide()).toHaveAttribute("data-anchor", "title-bar");
    expect(guide()).toHaveStyle({ top: "100px", left: "100px" });
    expect(screen.getByTestId("guide-highlight")).toBeInTheDocument();
  });

  it("keyboard only: focus moves into each step, Enter walks Next → Done, and the guide is stored", async () => {
    await open();
    for (let i = 1; i <= 4; i++) {
      expect(step()).toBe(`Step ${i} of 4`);
      expect(guide()).toHaveFocus();
      const next = button(i === 4 ? "Done" : "Next");
      next.focus();
      // A focused button activates on Enter; jsdom needs the click it would produce.
      fireEvent.keyDown(next, { key: "Enter" });
      fireEvent.click(next);
    }
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(localStorage.getItem(GUIDE_KEY)).toBe("done");
  });

  it("Back returns to the previous step and Escape skips", async () => {
    await open();
    fireEvent.click(button("Next"));
    fireEvent.click(button("Next"));
    expect(step()).toBe("Step 3 of 4");
    fireEvent.click(button("Back"));
    expect(step()).toBe("Step 2 of 4");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(localStorage.getItem(GUIDE_KEY)).toBe("done");
  });

  it("Reopen: the ? button shows step 1 of 4 again after finishing", async () => {
    localStorage.setItem(GUIDE_KEY, "done");
    await open();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "How to use the board" }));
    expect(step()).toBe("Step 1 of 4");
  });

  it("with storage unavailable it opens on each page load", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    const view = await open();
    fireEvent.click(button("Skip"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    view.unmount();
    await open();
    expect(step()).toBe("Step 1 of 4");
  });

  it("animates only when motion is allowed", async () => {
    await open();
    const animated = [...guide().classList].filter((c) => c.includes("transition"));
    expect(animated.length).toBeGreaterThan(0);
    expect(animated.every((c) => c.startsWith("motion-safe:"))).toBe(true);
  });
});
