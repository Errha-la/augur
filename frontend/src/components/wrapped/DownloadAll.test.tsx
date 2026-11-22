import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { wrappedResponse } from "../../test/builders";
import { WrappedOverlay } from "./WrappedOverlay";

const toPng = vi.hoisted(() =>
  vi.fn(async (node: HTMLElement, _options?: Record<string, unknown>) => `data:image/png;base64,${btoa(node.dataset.card ?? "")}`),
);
vi.mock("html-to-image", () => ({ toPng }));

const zips = vi.hoisted(() => [] as { files: Map<string, { data: string; options: unknown }> }[]);
vi.mock("jszip", () => ({
  default: class FakeZip {
    files = new Map<string, { data: string; options: unknown }>();
    constructor() {
      zips.push(this);
    }
    file(name: string, data: string, options: unknown) {
      this.files.set(name, { data, options });
      return this;
    }
    async generateAsync() {
      return new Blob(["zip"], { type: "application/zip" });
    }
  },
}));

let clicked: HTMLAnchorElement[];

beforeEach(() => {
  toPng.mockClear();
  zips.length = 0;
  Object.defineProperty(document, "fonts", { configurable: true, value: { ready: Promise.resolve() } });
  clicked = [];
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    clicked.push(this);
  });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:zip"), revokeObjectURL: vi.fn() }));
});

afterEach(() => {
  Reflect.deleteProperty(document, "fonts");
});

describe("Download all cards", () => {
  // specs/wrapped-zip-export — Scenario: Zip contents
  it("saves augur-wrapped-<race>.zip with the 7 cards as 1080×1920 PNGs named as for single download", async () => {
    render(<WrappedOverlay state={{ status: "open", data: wrappedResponse() }} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Download all" }));

    await waitFor(() => expect(clicked).toHaveLength(1));
    expect(clicked[0].download).toBe("augur-wrapped-2024-24-abu-dhabi-grand-prix.zip");
    expect(clicked[0].href).toBe("blob:zip");

    expect(zips).toHaveLength(1);
    const names = [...zips[0].files.keys()];
    expect(names).toHaveLength(7);
    expect(names[0]).toBe("augur-wrapped-2024-24-abu-dhabi-grand-prix-1-summary.png");
    expect(names[6]).toBe("augur-wrapped-2024-24-abu-dhabi-grand-prix-7-driver.png");
    for (const [i, name] of names.entries()) {
      expect(name).toMatch(new RegExp(`^augur-wrapped-2024-24-abu-dhabi-grand-prix-${i + 1}-[a-z-]+\\.png$`));
      expect(zips[0].files.get(name)!.options).toEqual({ base64: true });
    }

    expect(toPng).toHaveBeenCalledTimes(7);
    for (const call of toPng.mock.calls) {
      expect(call[1]).toMatchObject({ width: 1080, height: 1920, pixelRatio: 1 });
    }
    // Each PNG is the card it is named after.
    const slug = (name: string) => name.replace(/^.*-\d-/, "").replace(".png", "");
    for (const name of names) expect(atob(zips[0].files.get(name)!.data)).toBe(slug(name));
    // The off-screen export cards are gone again; only the visible card remains.
    await waitFor(() => expect(screen.queryAllByTestId("export-card")).toHaveLength(0));
    expect(screen.getAllByTestId("wrapped-card")).toHaveLength(1);
  });

  it("keeps the visible card and shows an error when an export fails", async () => {
    toPng.mockRejectedValueOnce(new Error("canvas tainted"));
    render(<WrappedOverlay state={{ status: "open", data: wrappedResponse() }} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Download all" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save the cards");
    expect(clicked).toHaveLength(0);
    expect(screen.getByTestId("wrapped-card").dataset.index).toBe("1");
    await act(async () => {});
  });
});
