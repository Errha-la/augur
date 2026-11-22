## Context

The user ordered the work in stages by importance. Stage 1 is the core replay, models, position prediction, and dashboard; Stage 2 is outcomes, benchmark, and Wrapped; Stage 3 is Gemini commentary and this change. Each item here extends a finished component and can ship alone.

## Goals / Non-Goals

**Goals:**

- Each of the five items is independently shippable and testable.

**Non-Goals:**

- Outcome rules for `overcut_window` (its outcome stays null).
- New API endpoints other than `/api/settings`.
- Entering, storing, or displaying API keys in the browser.
- Selecting live data before a `LiveFeed` exists (the option is shown disabled).
- Animated Wrapped cards.

## Decisions

### Overcut detector on the event engine

`overcut_window` fires at lap N when the car directly ahead of driver D (order after lap N-1) pitted on lap N, D did not pit on lap N (both stopping leaves nobody staying out), D was less than 3.0 s behind it at lap N-1, and D's `deg_s_per_lap` is below 0.05; once per pair per stop; severity 55. `EventEngine` keeps the previous lap's car states for the lap N-1 order and gaps, so the detector reads only laps up to N. Its template names both drivers, the gap before the stop, and D's degradation (a negative fit is worded as lap times still falling, measured: LEC -0.063 s per lap at Abu Dhabi lap 34), and its `next` adds D's best Monte Carlo strategy, in the same conditional voice as other events. The dashboard labels it OVERCUT and shows D's strategy table like the undercut card. Measured 2026-11-21 with lightgbm: 2 events at Abu Dhabi, 0 at Bahrain.

### Prediction lines from a per-race cache

For each lap k from 2 to N, the chart's dashed line uses `predicted_next_lap_s` from `/predictions?lap=k-1`. The frontend keeps a per-race cache and requests only missing laps up to N, so no request exceeds the current lap.

### Row animation with motion

Timing rows use motion's layout animation with ease `cubic-bezier(0.2, 1, 0.2, 1)` and 0.75 s, the values in the `race-dashboard` design source table.

### Zip export with jszip

"Download all" renders each of the 7 cards with the existing html-to-image export and adds them to a zip named `augur-wrapped-<race_id>.zip`.

### Server-side settings with secrets kept out of the browser

Runtime settings live in `data/settings.json` with three keys: `model`, `commentary_lang`, `data_source`. The value in that file wins over the environment variable (`AUGUR_MODEL`, `AUGUR_COMMENTARY_LANG`), which wins over the built-in default (`lightgbm`, `en`, `replay`). Every endpoint that reads the served model or commentary language reads it through one `augur.settings.current(data_dir)` function, so a change applies to the next request without a restart. The commentary language from it is also the language `/events` uses to look up cached commentary (`serving_key`) and the language `augur.narrate` passes to the narrator, so switching to 繁體中文 shows the zh-TW cache instead of silently dropping commentary.

The commentary narrator stays a server setting (user decision 2026-11-21): `AUGUR_NARRATOR`, `AUGUR_LLM_BASE_URL`, `AUGUR_LLM_MODEL`, `AUGUR_LLM_API_KEY`, `GEMINI_API_KEY`, and `GEMINI_MODEL` live in the server environment or a git-ignored `.env`. The API reports only a read-only `commentary` status: `narrator`, `llm_model`, `configured` (the narrator's required variable is set: `AUGUR_LLM_BASE_URL` for `openai_compat`, `GEMINI_API_KEY` for `gemini`), and `missing` (that variable's name when it is not set). It never returns a key, part of one, or the LLM server address. Alternative: let the panel switch the narrator. Rejected because it adds a writable server setting for little gain and the lab server address would pass through the browser.

### Settings panel as a side sheet

A gear button at the right end of the status bar opens a side sheet over the dashboard (no routing). It shows: model (a list of registered models with author, marked "not trained" and disabled when no model file exists), commentary language (English, 繁體中文), data source (Replay; Live disabled with "Coming later"), and the read-only commentary status (`openai_compat · glm — Configured`, `... — Not configured — set AUGUR_LLM_BASE_URL in .env`, or `Off — AUGUR_NARRATOR is none`). Saving calls `PUT /api/settings` and reloads the current lap's data.

## Implementation Contract

- Overcut: events of type `overcut_window` appear in `/events` with title, What / Why / Next, evidence, severity 55, and null outcome.
- Chart: dashed line per plotted driver, in its team colour; prediction requests never use a lap above N.
- Animation: rows move to new places on position change; no layout jump when the order is unchanged; `prefers-reduced-motion` turns the slide off.
- Zip: one file with 7 PNGs of 1080×1920.
- Settings API: `GET /api/settings` → `{model, commentary_lang, data_source, models: [{name, author, trained}], commentary_langs: ["en", "zh-TW"], data_sources: [{name: "replay", available: true}, {name: "live", available: false}], commentary: {narrator, llm_model, configured, missing}}`. `PUT /api/settings` accepts any subset of `model`, `commentary_lang`, `data_source`, writes `data/settings.json`, and returns the same shape as GET. Errors (422 with `detail`): `unknown model <name>`, `model <name> is not trained`, `unsupported language <lang>`, `live data is not available yet`, and `unknown field <field>` for any other key (including `narrator` and anything key-like such as `gemini_api_key`).
- Acceptance: `pytest backend` covers the overcut rule and template, settings precedence, and every settings error; `npm --prefix frontend run test` covers the chart requests, the animation wrapper, the zip contents, and the settings panel with mocks.
- Scope in: the five items. Scope out: anything else.

## Risks / Trade-offs

- [Prediction history adds one request per uncached lap] → cached per race; acceptable locally.
- [Animation at 4× playback (250 ms per lap) overlaps the 0.75 s transition] → motion interrupts and retargets running animations; checked manually at 4×.
