import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, SettingsRejected } from "../api/client";
import { fakeBackend, fixtures, type RequestCtx } from "../test/fakeBackend";
import { goToLap, renderApp } from "../test/renderApp";
import { notAnalyzedText } from "./Messages";
import { commentaryStatusText, SettingsSheet } from "./SettingsSheet";

afterEach(() => {
  vi.restoreAllMocks();
});

/** Fake handlers whose model follows the fake backend's current settings. */
function modelAwareHandlers(current: () => string, analyzed: (model: string) => boolean = () => true) {
  return {
    events: ({ raceId, lap }: RequestCtx) => ({
      ...fixtures.events,
      race_id: raceId,
      lap,
      model: current(),
      analyzed: analyzed(current()),
      events: analyzed(current()) ? fixtures.events.events.filter((e) => e.lap <= lap) : [],
    }),
    predictions: ({ raceId, lap }: RequestCtx) => ({ ...fixtures.predictions, race_id: raceId, lap, model: current() }),
  };
}

async function openSettingsAndPick(model: string) {
  fireEvent.click(screen.getByRole("button", { name: "Settings" }));
  const sheet = await screen.findByTestId("settings-sheet");
  const select = await within(sheet).findByRole("combobox", { name: "Model" });
  fireEvent.change(select, { target: { value: model } });
  fireEvent.click(within(sheet).getByRole("button", { name: "Save" }));
}

describe("Settings side sheet", () => {
  // specs/settings-panel — Scenario: Switch model
  it("saves baseline at lap 20 and re-fetches lap 20 from baseline", async () => {
    let model = () => "lightgbm";
    const { backend } = await renderApp({ handlers: modelAwareHandlers(() => model()) });
    model = () => backend.settings().model;
    await goToLap(20);

    const before = backend.requests.length;
    await openSettingsAndPick("baseline");

    await waitFor(() => expect(screen.queryByTestId("settings-sheet")).toBeNull());
    const put = backend.of("settings").find((r) => r.method === "PUT");
    expect(put?.body).toEqual({ model: "baseline", commentary_lang: "en", data_source: "replay" });

    await waitFor(() => {
      const after = backend.requests.slice(before);
      expect(after.some((r) => r.endpoint === "events" && r.lap === 20)).toBe(true);
      expect(after.some((r) => r.endpoint === "predictions" && r.lap === 20)).toBe(true);
    });
    expect(backend.settings().model).toBe("baseline");
  });

  // specs/settings-panel — Scenario: Model not analyzed for this race
  it("shows the Race not analyzed message after switching to a model that has not analyzed the race", async () => {
    let model = () => "lightgbm";
    const { backend } = await renderApp({ handlers: modelAwareHandlers(() => model(), (m) => m !== "baseline") });
    model = () => backend.settings().model;
    const raceId = backend.of("events")[0].raceId;

    await openSettingsAndPick("baseline");
    expect(await screen.findByText(notAnalyzedText(raceId))).toBeInTheDocument();
  });

  // specs/settings-panel — Scenario: Commentary status shown read-only
  it("shows the narrator status read-only, with no input for the narrator, a key, or a server address", async () => {
    fakeBackend();
    const { container } = render(<SettingsSheet onClose={() => {}} onSaved={() => {}} />);
    expect(await screen.findByTestId("commentary-status")).toHaveTextContent("openai_compat · glm — Configured");

    expect(container.querySelectorAll("input")).toHaveLength(0);
    expect(container.querySelector('[type="password"]')).toBeNull();
    const selects = screen.getAllByRole("combobox").map((s) => s.getAttribute("aria-label"));
    expect(selects).toEqual(["Model", "Commentary language", "Data source"]);
    expect(screen.queryByRole("combobox", { name: /narrator/i })).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("marks untrained models and Live as unavailable, and labels the languages", async () => {
    fakeBackend();
    render(<SettingsSheet onClose={() => {}} onSaved={() => {}} />);
    const model = await screen.findByRole("combobox", { name: "Model" });
    const untrained = within(model).getByRole("option", { name: /mymodel/ });
    expect(untrained).toBeDisabled();
    expect(untrained).toHaveTextContent("(not trained)");
    const live = within(screen.getByRole("combobox", { name: "Data source" })).getByRole("option", { name: /Live/ });
    expect(live).toBeDisabled();
    expect(live).toHaveTextContent("Coming later");
    const langs = within(screen.getByRole("combobox", { name: "Commentary language" })).getAllByRole("option");
    expect(langs.map((o) => o.textContent)).toEqual(["English", "繁體中文"]);
  });

  it("shows a 422 detail next to Save and keeps the sheet open", async () => {
    fakeBackend();
    vi.spyOn(api, "putSettings").mockRejectedValue(new SettingsRejected("model baseline is not trained"));
    const onSaved = vi.fn();
    render(<SettingsSheet onClose={() => {}} onSaved={onSaved} />);
    await screen.findByRole("combobox", { name: "Model" });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByTestId("settings-error")).toHaveTextContent("model baseline is not trained");
    expect(onSaved).not.toHaveBeenCalled();
    expect(screen.getByTestId("settings-sheet")).toBeInTheDocument();
  });

  it.each([
    [{ narrator: "openai_compat", llm_model: "glm", configured: true, missing: null }, "openai_compat · glm — Configured"],
    [
      { narrator: "openai_compat", llm_model: "glm", configured: false, missing: "AUGUR_LLM_BASE_URL" },
      "openai_compat · glm — Not configured — set AUGUR_LLM_BASE_URL in .env",
    ],
    [
      { narrator: "gemini", llm_model: "gemini-flash-latest", configured: false, missing: "GEMINI_API_KEY" },
      "gemini · gemini-flash-latest — Not configured — set GEMINI_API_KEY in .env",
    ],
    [{ narrator: "none", llm_model: null, configured: false, missing: null }, "Off — AUGUR_NARRATOR is none"],
  ])("commentary status %#", (status, text) => {
    expect(commentaryStatusText(status)).toBe(text);
  });
});
