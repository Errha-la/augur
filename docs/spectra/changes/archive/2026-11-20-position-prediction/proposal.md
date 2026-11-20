## Why

AUGUR's goal is to be a viewer's position-prediction tool beyond the broadcast and ordinary race trackers: at any lap, how likely is each driver to win, reach the podium, or score points. The lap-time model, degradation fits, and pit-loss estimate from `prediction-and-events` already describe each car's future pace; this change combines them into a full-field race simulation.

This change is the backend track of Stage 1 in `AGENTS.md`. It runs in parallel with `race-dashboard` (the frontend track), whose mock responses follow this change's API contract until these endpoints are served.

## What Changes

- Add a seeded full-field Monte Carlo simulator that runs the remaining laps for every driver from lap N, using predicted pace, stint degradation, fuel effect, expected pit stops, and a dirty-air penalty that makes passing hard.
- Output per driver: win, podium, and points probabilities, expected finishing position, and its p10-p90 range.
- Store predictions for every lap when a race is analyzed, and serve them per lap and as a history up to lap N, with an `analyzed` flag present in every response so the frontend mocks and the real backend have one fixed shape.
- Run as the Stage 1 backend track: in its own worktree, changing only `backend/`.

## Non-Goals

Recorded in design.md.

## Capabilities

### New Capabilities

- `position-prediction`: Simulate the rest of the race from lap N for the whole field and serve finishing-position probabilities per lap.

### Modified Capabilities

(none)

## Impact

- New code, all under `backend/`: backend/src/augur/positions.py (simulator), a step in the existing `python -m augur.analyze` command, two routes in the FastAPI app, backend/tests/.
- New SQLite table `position_predictions` in data/augur.sqlite (git-ignored runtime data, written by the analyze command; no tracked file outside `backend/`).
- Not changed by this track: `frontend/`, the root `README.md`, and any other path outside `backend/`. Spectra artifacts in `docs/spectra/` are synced by hand as `AGENTS.md` describes.
- Contract consumer: change `race-dashboard` builds its mocks from the API contract in design.md; a change to field names needs both changes updated first.
- Depends on `race-data-replay` (`RaceFeed`) and `prediction-and-events` (model registry, degradation fits, pit-loss estimate, analyze command); both are archived on `main` (archive commit 53c1575), so the track may start.
