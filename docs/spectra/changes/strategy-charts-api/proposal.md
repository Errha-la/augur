## Why

The strategy charts planned for the dashboard (race trace, pit-stop clock, pit-window curve, tyre stints, degradation by compound, position fan and heatmap) need data that no endpoint serves today: race-time deltas per lap, where a driver would rejoin after a stop, expected race time for every possible pit lap, stint spans, and the full finishing-position distribution. Strategy teams use these views to read a race; AUGUR's dashboard can only show tables and one lap chart. This is the BE-2 track of Stage 4 Wave 1 in `AGENTS.md`, so `strategy-chart-widgets` (Wave 2) can build on a fixed contract.

## What Changes

- New module `augur.charts` with pure functions that read only laps up to the replay lap.
- New endpoints under `/api/races/{race_id}/`:
  - `trace?lap=N`: race trace, each driver's time gained or lost against a reference pace per lap.
  - `rejoin?lap=N&driver=D`: every car's gap to the leader and where D would rejoin if D pitted now (data for the pit-stop clock).
  - `pit-window?lap=N&driver=D[&runs&seed]`: expected remaining race time for every possible pit lap, built on `strategy.simulate_pit_laps()` from `position-sim-calibration`.
  - `stints?lap=N`: each driver's stints so far.
  - `degradation?lap=N`: fuel-corrected clean laps by tyre age per compound with a fitted line.
  - `positions/distribution?lap=N`: the stored finishing-position distribution from `position-sim-calibration`.
- `positions/history` gains `position_p10` and `position_p90` per driver for the position fan.

## Non-Goals (optional)

Recorded in design.md.

## Capabilities

### New Capabilities

- `strategy-charts-api`: chart-data endpoints for race trace, pit rejoin, pit window, stints, degradation points, and position distribution.

### Modified Capabilities

- `position-prediction`: the `positions/history` response adds `position_p10` and `position_p90`.

## Impact

- Affected specs: `strategy-charts-api` (new), `position-prediction` (modified).
- Affected code:
  - New: backend/src/augur/charts.py, backend/tests/test_charts.py, backend/tests/test_charts_api.py
  - Modified: backend/src/augur/api.py, backend/tests/test_positions_api.py
- Depends on `position-sim-calibration` tasks 1.1 (`strategy.simulate_pit_laps`) and 2.4 (stored `position_distribution`) being merged to `main` before the pit-window and distribution tasks start.
- The frontend `race-dashboard` mocks for `positions/history` keep working: the two new fields are additions.
