import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { NumberLink } from "../../api/types";
import { LinkedText } from "./LinkedText";

const gap: NumberLink = { start: 7, end: 10, field: "gap_s", chart: "trace", drivers: ["NOR", "PIA"] };

describe("LinkedText", () => {
  // Scenario: Plain text without links
  it("renders text with empty links as plain text with no buttons", () => {
    const { container } = render(<p><LinkedText text="Old tyres, 14 laps." links={[]} /></p>);
    expect(container).toHaveTextContent("Old tyres, 14 laps.");
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    render(<p><LinkedText text="No links field." /></p>);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("turns each linked number into a button named '<number>: show on chart'", () => {
    const onClick = vi.fn();
    const { container } = render(<p><LinkedText text="NOR is 1.8 s behind PIA on lap 20." links={[gap]} onLinkClick={onClick} /></p>);
    expect(container).toHaveTextContent("NOR is 1.8 s behind PIA on lap 20.");
    const button = screen.getByRole("button", { name: "1.8: show on chart" });
    expect(button).toHaveAttribute("aria-haspopup", "dialog");
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledWith(gap, 0, "1.8", button);
  });

  it("uses code-point offsets for Chinese commentary", () => {
    const link = { ...gap, start: 11, end: 14 };
    const { container } = render(<p><LinkedText text="NOR 落後 PIA 1.8 秒" links={[link]} /></p>);
    expect(screen.getByRole("button", { name: "1.8: show on chart" })).toHaveTextContent("1.8");
    expect(container).toHaveTextContent("NOR 落後 PIA 1.8 秒");
  });

  it("keeps code points intact around characters outside the BMP", () => {
    // "🏁" is one code point but two UTF-16 units: offsets stay code points.
    const link = { ...gap, start: 2, end: 5 };
    render(<p><LinkedText text="🏁 2.5 s" links={[link]} /></p>);
    expect(screen.getByRole("button", { name: "2.5: show on chart" })).toBeInTheDocument();
  });

  it("drops links outside the text or overlapping an earlier one", () => {
    const links = [gap, { ...gap, start: 8, end: 9 }, { ...gap, start: 30, end: 99 }];
    render(<p><LinkedText text="NOR is 1.8 s behind PIA on lap 20." links={links} /></p>);
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("marks the open link as expanded", () => {
    render(<p><LinkedText text="NOR is 1.8 s behind PIA on lap 20." links={[gap]} openIndex={0} /></p>);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
  });
});
