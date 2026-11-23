import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";
import { preset } from "../canvas/presets";
import { fakeBackend } from "../test/fakeBackend";
import { waitForShown } from "../test/renderApp";
import { EMPTY_BOARD } from "./Board";

async function showApp() {
  fakeBackend();
  render(<App />);
  await waitForShown(1);
}

function openMenu() {
  fireEvent.click(screen.getByRole("button", { name: "Board menu" }));
  return within(screen.getByRole("menu", { name: "Board menu" }));
}

function closeMenu() {
  fireEvent.keyDown(document, { key: "Escape" });
}

function choose(name: string | RegExp) {
  fireEvent.click(openMenu().getByRole("menuitem", { name }));
}

function selectBoard(name: string | RegExp) {
  fireEvent.click(openMenu().getByRole("menuitemradio", { name }));
}

function widgetCells() {
  return screen.getAllByTestId("widget").map((w) => [w.dataset.widgetType, w.dataset.cell]);
}

function presetCells(id: "pit" | "battle" | "pace") {
  return preset(id).widgets.map((w) => [w.type, `${w.x},${w.y},${w.w},${w.h}`]);
}

describe("Board menu", () => {
  it("opens BATTLE first and lists the three presets", async () => {
    await showApp();
    expect(screen.getByTestId("board-menu-label")).toHaveTextContent("BATTLE");
    expect(widgetCells()).toEqual(presetCells("battle"));
    const names = openMenu()
      .getAllByRole("menuitemradio")
      .map((b) => b.textContent);
    // "●" marks the active board.
    expect(names).toEqual(["PIT WALL", "●BATTLE", "PACE"]);
  });

  it("Reset an edited preset: removing a widget marks PIT WALL edited until it is reset", async () => {
    await showApp();
    selectBoard("PIT WALL");
    fireEvent.click(screen.getAllByRole("button", { name: "Remove Timing widget" })[0]);
    expect(screen.getByTestId("board-menu-label")).toHaveTextContent(/PIT WALL\s*edited/);
    expect(widgetCells()).toHaveLength(3);
    choose("Reset to preset");
    expect(screen.getByTestId("board-menu-label")).not.toHaveTextContent("edited");
    expect(widgetCells()).toEqual(presetCells("pit"));
    expect(openMenu().queryByRole("menuitem", { name: "Reset to preset" })).not.toBeInTheDocument();
  });

  it("Blank board: 'New blank board' with no custom boards makes an empty 'Board 1' active", async () => {
    await showApp();
    choose("New blank board");
    expect(screen.getByTestId("board-menu-label")).toHaveTextContent("Board 1");
    expect(screen.queryAllByTestId("widget")).toHaveLength(0);
    expect(screen.getByText(EMPTY_BOARD)).toBeInTheDocument();
  });

  it("Delete active board: asks in the page, then removes it and switches to BATTLE", async () => {
    await showApp();
    choose("New blank board");
    expect(openMenu().queryByRole("menuitem", { name: "Delete" })).toBeInTheDocument();
    closeMenu();
    choose("Delete");
    const confirm = within(screen.getByRole("alertdialog", { name: "Confirm delete" }));
    expect(confirm.getByText(/Delete Board 1\?/)).toBeInTheDocument();
    fireEvent.click(confirm.getByRole("button", { name: "Delete" }));
    expect(screen.getByTestId("board-menu-label")).toHaveTextContent("BATTLE");
    expect(openMenu().queryByRole("menuitemradio", { name: /Board 1/ })).not.toBeInTheDocument();
  });

  it("Cancel in the delete confirmation keeps the board; presets offer no Delete", async () => {
    await showApp();
    expect(openMenu().queryByRole("menuitem", { name: "Delete" })).not.toBeInTheDocument();
    closeMenu();
    choose("New blank board");
    choose("Delete");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("menuitem", { name: "Delete" })).toBeInTheDocument();
    closeMenu();
    expect(screen.getByTestId("board-menu-label")).toHaveTextContent("Board 1");
  });

  it("Rename and Duplicate", async () => {
    await showApp();
    choose("Duplicate");
    expect(screen.getByTestId("board-menu-label")).toHaveTextContent("BATTLE copy");
    expect(widgetCells()).toEqual(presetCells("battle"));
    choose("Rename");
    fireEvent.change(screen.getByRole("textbox", { name: "Board name" }), { target: { value: "My battle" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByTestId("board-menu-label")).toHaveTextContent("My battle");
  });
});
