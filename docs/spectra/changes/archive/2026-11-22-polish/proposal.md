## Why

Four features were moved out of the core changes so the two-day build ships the essentials first: the overcut detector, predicted-lap lines in the chart, row slide animation, and a one-click download of all Wrapped cards. The user also asked for a settings panel, because today the served model and commentary language can only be changed through environment variables and a server restart. None of these block other work, so they form the last stage.

## What Changes

- Add the `overcut_window` event detector with its own analysis template.
- Add dashed predicted-lap lines to the lap-time chart.
- Animate timing rows to their new places when positions change.
- Add "Download all" to the Wrapped overlay, saving every card in one zip.
- Add a settings panel (opened from a gear button in the status bar) and `GET`/`PUT /api/settings` to choose the served model, the commentary language, and the data source, and to show whether Gemini is configured. API keys are never entered or shown in the browser.

## Non-Goals

Recorded in design.md.

## Capabilities

### New Capabilities

- `overcut-detection`: Detect overcut opportunities when the car ahead pits and explain them.
- `chart-predictions`: Show the lap-time prediction made before each lap next to the actual lap time.
- `timing-animation`: Animate position changes in the timing list.
- `wrapped-zip-export`: Download all Wrapped cards as one zip file.
- `settings-panel`: View and change runtime settings (model, commentary language, data source) from the dashboard, with secrets kept on the server.

### Modified Capabilities

(none)

## Impact

- Backend: one detector and one template added to the existing event engine; new `GET /api/settings` and `PUT /api/settings`; settings stored in data/settings.json, which takes precedence over the `AUGUR_MODEL` and `AUGUR_COMMENTARY_LANG` environment variables.
- Frontend: lap-time chart, timing list, Wrapped overlay, settings panel; new dependencies motion and jszip.
- Depends on `prediction-and-events`, `race-dashboard`, `race-wrapped`, and `llm-commentary`.
