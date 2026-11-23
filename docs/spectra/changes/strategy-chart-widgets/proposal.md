## Why

The backend now serves chart data for the race trace, pit-stop clock, pit-window curve, tyre stints, degradation by compound, and the finishing-position distribution (`strategy-charts-api`, archived 2026-11-23), but the dashboard still shows only tables and one lap chart. This is Wave 2 of Stage 4 in `AGENTS.md`: turn that data into board widgets so a viewer can read the race the way a strategy team does, and place them in the presets.

## What Changes

- Eight new widget types on the dashboard board: `trace` (race trace), `pitclock` (pit-stop clock with the rejoin slot), `pitwindow` (expected race time per pit lap), `stints` (tyre stints per driver), `degradation` (fuel-corrected lap time by tyre age per compound with a fitted line), `pace` (fuel-corrected lap times of up to four drivers on one chart), `fan` (expected finishing position with its p10-p90 band over the laps so far), and `heatmap` (finishing-position probabilities, drivers by positions).
- `pitclock`, `pitwindow`, and `fan` have the per-widget driver setting (follow focus by default, or pinned). `pace` has a driver list setting (follow the focus driver and its neighbours by default, or up to four pinned codes).
- A fourth preset, STRATEGY, with the pit window, pit clock, stints, degradation, and race trace. PIT WALL, BATTLE, and PACE each swap one existing widget for the most relevant new chart. Edited presets keep the viewer's copy.
- The focus panel note under the position probabilities changes from "Assumes a green race to the end" to a note that the probabilities include safety-car and VSC periods (the position simulator simulates them since `position-sim-calibration`); the strategy table keeps a green-race note, because the strategy simulator still assumes a green race.
- Typed API client functions for `trace`, `rejoin`, `pit-window`, `stints`, `degradation`, and `positions/distribution`, plus the `position_p10` and `position_p90` history fields.

## Capabilities

### New Capabilities

- `strategy-chart-widgets`: the eight chart widgets, what each shows at replay lap N, their empty and error states, and when each requests data.

### Modified Capabilities

- `dashboard-canvas`: the widget type list grows by eight types; the per-widget driver setting applies to the new driver widgets; presets become four (adds STRATEGY, changes one widget in each existing preset).
- `focus-driver`: the note under the position probabilities changes; the strategy table gets the green-race note.

## Impact

- Affected code: frontend/src/api/ (client.ts, types.ts), frontend/src/canvas/ (registry.ts, board.ts, sanitize.ts, presets.ts), frontend/src/App.tsx (widget rendering), frontend/src/components/FocusPanel.tsx (notes), frontend/src/components/StrategyTable.tsx (notes), new chart components under frontend/src/components/charts/, and their Vitest tests.
- APIs: consumes the six `strategy-charts-api` endpoints; no backend change.
- Dependencies: none added; charts use the existing Recharts 3, the heatmap and pit clock are plain SVG/CSS.
- Stored boards: existing `augur.boards.v1` data stays valid; unedited presets show the new definitions, edited presets keep the viewer's copy.
- README: notes go to tasks.md for `portfolio-release`.
