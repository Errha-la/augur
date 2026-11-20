## Why

AUGUR makes predictions during a replay, but it never says whether they were right. A model that is meant to be cloned and improved needs an honest scoreboard, and the scoreboard is only shared if it looks good. This change scores the headline output (finishing-position probabilities), the lap-time model, and the event calls against what actually happened, and turns the result into a shareable end-of-race "Wrapped" story in Instagram story format.

## What Changes

- Resolve `undercut_window` and `degradation_warning` events into outcomes (hit, miss, void) during analysis, and reveal each outcome in the API only once the replay reaches the lap where it was decided.
- Add shared scoring: podium-probability skill against a "current order holds" baseline at three checkpoints (headline), lap-time MAE improvement over the baseline model (second), and event hit rate (third).
- Add `python -m augur.bench --model <name>` that scores a model on the fixed benchmark races (2024 rounds 1 and 24) and writes `bench/<name>.json`.
- Add `GET /api/races/{race_id}/wrapped` that unlocks only at the final lap and returns the race summary, the podium call, the scores, the best call, the biggest miss, the biggest moment, and a card for one chosen driver.
- Add a full-screen story of 7 Wrapped cards in the dashboard, opened from the status bar at the final lap, with each card downloadable as a 1080×1920 PNG.

## Non-Goals

Recorded in design.md.

## Capabilities

### New Capabilities

- `event-outcomes`: Decide whether undercut and degradation events came true, and reveal each outcome only after the replay passes its deciding lap.
- `model-benchmark`: Score any registered lap-time model on the fixed benchmark races with a reproducible JSON result.
- `race-wrapped-api`: Serve the end-of-race Wrapped summary once the replay reaches the final lap.
- `wrapped-story`: Show the Wrapped as full-screen story cards and export them as Instagram-story-sized PNG files.

### Modified Capabilities

(none)

## Impact

- Backend: new modules backend/src/augur/events/outcomes.py, backend/src/augur/scoring.py, backend/src/augur/bench.py, a new route in the existing FastAPI app; new nullable columns `outcome`, `outcome_lap`, `outcome_text` in the SQLite `events` table; the `/events` response gains the same three fields.
- Frontend: new Wrapped components under frontend/src/; new dependency html-to-image (JetBrains Mono is already loaded by the dashboard through @fontsource-variable/jetbrains-mono).
- New tracked directory `bench/` for benchmark result files.
- Depends on `race-data-replay`, `prediction-and-events` (model registry, analyze command, events table), `position-prediction` (`position_predictions` table), and `race-dashboard` (status bar, design tokens, focus driver).
