## Why

AUGUR's event analysis is accurate but reads like a data sheet. Viewers expect commentary in the voice of a race analyst. The user plans to use an LLM for this: first the self-hosted `glm` model on the lab's OpenAI-compatible server, and Gemini when a key and capacity are available. Race data is public, so sending event evidence to either is acceptable, as long as every number in the commentary stays grounded in AUGUR's own computed evidence.

## What Changes

- Add a `Narrator` interface with a Gemini implementation and an OpenAI-compatible implementation (for self-hosted servers such as the lab `glm`) that turn one event's evidence and template analysis into a short commentator-style paragraph.
- Select the narrator with `AUGUR_NARRATOR` (default `gemini`).
- Reject any generated commentary that contains a number or driver code not present in the event's evidence or template text, and keep the template analysis as the fallback.
- Add `python -m augur.narrate --race <race_id>` that generates and caches commentary for a race's events; analysis, tests, and the benchmark never need an API key or LLM server.
- Return `commentary` with each event and a top-level `commentary_model` in `/events`, and show the commentary in the dashboard's primary event card.

## Non-Goals

Recorded in design.md.

## Capabilities

### New Capabilities

- `event-commentary`: Generate, ground-check, cache, and serve LLM commentary for detected race events.

### Modified Capabilities

(none)

## Impact

- New code: backend/src/augur/narration/ (protocol, Gemini narrator, OpenAI-compatible narrator, grounding check, cache), backend/src/augur/narrate.py (command), fields added to the `/events` response, a commentary block in the frontend primary event card.
- New dependency: google-genai (backend). The OpenAI-compatible narrator uses the Python standard library.
- New environment variables: `AUGUR_NARRATOR` (default `gemini`), `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-flash-latest`), `AUGUR_LLM_BASE_URL`, `AUGUR_LLM_MODEL` (default `glm`), `AUGUR_LLM_API_KEY` (optional), `AUGUR_COMMENTARY_LANG` (default `en`).
- New SQLite table `commentary`.
- AGENTS.md: the hard rule about Gemini commentary is reworded to cover both narrators.
- Depends on `prediction-and-events` (events and analysis) and `race-dashboard` (primary event card).
