## Why

The backend from `race-data-replay`, `prediction-and-events`, and `position-prediction` answers what happened, why, what next, and who is likely to finish where, but only as JSON. A portfolio viewer needs to see a race unfold lap by lap with the most important analysis in focus, and to follow one driver closely. This change adds that dashboard, styled after the open-source live-timing dashboard BENNNZO/f1-dashboard.

## What Changes

- Add a React + Vite + TypeScript single-page app in `frontend/`, styled with Tailwind CSS 4 in a dark timing-screen look (zinc palette, JetBrains Mono, compound colours, team-colour stripes).
- Add a status bar with race selection, lap count, track status, and replay controls (slider, step, play/pause, speed) that drive every panel.
- Add a timing list ordered by position, showing tyre, gap, last lap, predicted next lap, degradation, and win and podium probabilities.
- Add a focus-driver panel: pick one driver to follow and see their stint history, degradation, predicted next lap, finishing-position probabilities with their trend over the race, live strategy table, and the events that involve them.
- Add a lap-time chart of actual lap times for the focus driver and the cars directly ahead and behind, up to the current lap.
- Add a central intelligence panel: the newest most severe event is expanded as the primary analysis (What / Why / Next, evidence, strategy table); earlier events collapse into an event history; an event timeline jumps to a lap; events involving the focus driver are highlighted.
- Add clear messages when the backend is unreachable, no race is ingested, or the race is not analyzed.

## Non-Goals

Recorded in design.md.

## Capabilities

### New Capabilities

- `replay-controls`: Choose a race and move through it lap by lap, manually or by playback, with backend status messages.
- `race-overview`: Show the per-driver timing list with position probabilities and the lap-time chart at the current lap.
- `focus-driver`: Follow one chosen driver with a dedicated panel and highlights across the dashboard.
- `intelligence-panel`: Show the primary event analysis, the collapsed event history, and the clickable event timeline.

### Modified Capabilities

(none)

## Impact

- New code: frontend/ (Vite config, src/ components, API client, tests).
- New dependencies: react, react-dom, vite, typescript, tailwindcss, @tailwindcss/vite, recharts; dev: vitest, @testing-library/react, jsdom.
- Uses the existing endpoints `/api/races`, `/state`, `/laps`, `/predictions`, `/events`, `/strategy`, `/positions`, `/positions/history`; no backend changes.
