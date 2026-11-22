## 1. Backend

- [x] 1.1 Implement the Overcut window event following Overcut detector on the event engine: detector registered in `EventEngine`, dedupe per pair per stop, severity 55, template with the best Monte Carlo strategy in `next`, null outcome. Verify: unit test for every row of the "conditions" table and a template test for conditional wording.
- [x] 1.2 Implement Settings precedence and the Settings API following Server-side settings with secrets kept out of the browser: `augur.settings.current()` used by every endpoint that reads the served model or commentary language, `data/settings.json` persistence, the settings commentary language passed to `serving_key` and `augur.narrate`, `GET`/`PUT /api/settings` with forbidden extra fields and the read-only `commentary` status. Verify: tests for every row of the "model resolution", "PUT cases", and "commentary status" tables, "Commentary language follows settings", and "Secrets never exposed".

## 2. Frontend

- [x] 2.1 Add Predicted lap lines to the lap-time chart following Prediction lines from a per-race cache. Verify: component test for "Cached history" asserting the exact requested laps and that none exceeds the current lap.
- [x] 2.2 Add Animated position changes to the timing list following Row animation with motion. Verify: component test with a mocked motion `layout` prop for "Two drivers swap"; manual check at 4× playback recorded in the task notes.
- [x] 2.3 Add Download all cards to the Wrapped overlay following Zip export with jszip. Verify: component test with mocked html-to-image and jszip for "Zip contents".
- [x] 2.4 [after: 1.2] Implement the Settings side sheet following Settings panel as a side sheet: gear button, model list with trained state, language, data source with disabled Live, read-only commentary status, no narrator/key/server input, save and reload of the current lap, inline 422 message. Verify: component tests for "Switch model", "Model not analyzed for this race", and "Commentary status shown read-only" with mocked fetch, and a test that the sheet has no password, key, narrator, or URL input.

## Change notes

- 2026-11-21: settings updated for llm-commentary's narrators (user decision: the narrator stays a server setting). `gemini_configured` is replaced by a read-only `commentary` status (`narrator`, `llm_model`, `configured`, `missing`), and the settings commentary language now reaches `/events` and `augur.narrate`. Supersedes: the original "Gemini status" in 1.2 and 2.4.
- 2026-11-21: 1.1 added a rule the spec lacked (no event when D also pits on lap N), wording for a negative degradation fit, and the OVERCUT label and strategy table in the dashboard; recorded in the overcut spec and design.
- 2026-11-21: 2.2 is implemented (motion layout on every row, `data-moved` on rows whose position changed, reduced motion respected) and waits for the user's manual check at 4× playback before it is checked off.
- 2026-11-22: 2.2 manual check by the user at 4× playback: OK.
