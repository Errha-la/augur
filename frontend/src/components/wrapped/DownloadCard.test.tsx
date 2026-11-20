import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { wrappedResponse } from "../../test/builders";
import { WrappedOverlay } from "./WrappedOverlay";

const toPng = vi.hoisted(() => vi.fn(async () => "data:image/png;base64,AAAA"));
vi.mock("html-to-image", () => ({ toPng }));

let releaseFonts: () => void;
let clicked: HTMLAnchorElement[];

beforeEach(() => {
  toPng.mockClear();
  const ready = new Promise<void>((resolve) => {
    releaseFonts = resolve;
  });
  Object.defineProperty(document, "fonts", { configurable: true, value: { ready } });
  clicked = [];
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    clicked.push(this);
  });
});

afterEach(() => {
  Reflect.deleteProperty(document, "fonts");
});

function open() {
  render(<WrappedOverlay state={{ status: "open", data: wrappedResponse() }} onClose={() => {}} />);
}

describe("Story card download", () => {
  // Scenario: Card export size
  it("saves card 4 of Abu Dhabi as a 1080×1920 PNG named after the card, after fonts are ready", async () => {
    open();
    for (let i = 1; i < 4; i++) fireEvent.keyDown(window, { key: "ArrowRight" });
    const card = screen.getByTestId("wrapped-card");
    expect(card.dataset.card).toBe("best-call");

    fireEvent.click(screen.getByRole("button", { name: "Download card" }));
    // Fonts still loading: nothing exported yet.
    await act(async () => {
      await Promise.resolve();
    });
    expect(toPng).not.toHaveBeenCalled();

    await act(async () => releaseFonts());
    await waitFor(() => expect(toPng).toHaveBeenCalledTimes(1));
    const [node, options] = toPng.mock.calls[0] as unknown as [HTMLElement, Record<string, unknown>];
    expect(node).toBe(card);
    expect(options).toMatchObject({ width: 1080, height: 1920, pixelRatio: 1 });

    await waitFor(() => expect(clicked).toHaveLength(1));
    expect(clicked[0].download).toBe("augur-wrapped-2024-24-abu-dhabi-grand-prix-4-best-call.png");
    expect(clicked[0].href).toBe("data:image/png;base64,AAAA");
  });

  it("shows an error when the export fails, and the card stays open", async () => {
    toPng.mockRejectedValueOnce(new Error("canvas tainted"));
    open();
    fireEvent.click(screen.getByRole("button", { name: "Download card" }));
    await act(async () => releaseFonts());
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save the card");
    expect(screen.getByTestId("wrapped-card")).toBeInTheDocument();
    expect(clicked).toHaveLength(0);
  });

  it("does not turn the card when the download button is clicked", async () => {
    open();
    fireEvent.click(screen.getByRole("button", { name: "Download card" }));
    expect(screen.getByTestId("wrapped-card").dataset.index).toBe("1");
    await act(async () => releaseFonts());
  });
});
