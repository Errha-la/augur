## Why

After `race-data-replay`, AUGUR can show what the timing screen showed, but it cannot yet explain why things happen or what could happen next. This change adds the models and the event engine that turn lap data into ranked, explained race events — the core of the portfolio story.

## What Changes

- Add leakage-safe feature engineering on the normalized laps (clean-lap filter, tyre age, fuel correction, rolling recent pace, a circuit degradation prior from the previous season at the same location, and the team's pace relative to the field).
- Add a pluggable lap-time model interface (`LapTimeModel` protocol plus a name registry) so anyone who clones AUGUR can drop in their own model; ship a LightGBM model and a naive baseline, trained on 2024 rounds 2-11 and evaluated on the 2024 demo races (rounds 1 and 24), with metrics written to a JSON file per model. The circuit prior for a 2024 race comes from the 2023 race at the same location, because OpenF1 (the only data source since `race-data-replay`) has no race sessions before 2023.
- Add per-stint tyre degradation fitting with performance-cliff detection.
- Add a seeded Monte Carlo pit-strategy simulator that compares "no further stop" with pitting on upcoming laps.
- Add an incremental event engine that consumes a `RaceFeed` lap by lap (so the same code later runs on live data), with rule-based detection of pace drop, degradation warning, undercut window, and position change, each with a deterministic What / Why / Next analysis written as an analyst's probabilistic outlook, and a severity score.
- Add a command that precomputes events lap by lap for a race into SQLite, and HTTP endpoints for predictions, strategy, and events at lap N.

## Non-Goals

Recorded in design.md.

## Capabilities

### New Capabilities

- `lap-time-prediction`: Pluggable models that are trained, evaluated, and served as next-lap time predictions per driver at a replay lap.
- `tyre-degradation`: Estimate the current stint's degradation rate per driver and flag performance cliffs.
- `strategy-simulation`: Compare pit strategies for one driver at a replay lap with a seeded Monte Carlo simulation.
- `race-event-detection`: Detect significant race events lap by lap, attach explained analysis, and serve them up to a replay lap.

### Modified Capabilities

(none)

## Impact

- New code: backend/src/augur/features.py, backend/src/augur/models/ (laptime, degradation), backend/src/augur/strategy.py, backend/src/augur/events/ (detectors, analysis, precompute), new routes in the existing FastAPI app, backend/tests/.
- New dependencies: lightgbm, scikit-learn, numpy, joblib.
- New local files: data/models/<model>.joblib, data/models/<model>_metrics.json; new SQLite table `events` (with a `model` column) in data/augur.sqlite.
- New environment variable `AUGUR_MODEL` (default `lightgbm`) selects the model the API serves.
- Depends on `race-data-replay` (`ReplayStore.laps_until`, OpenF1 ingest command, catalog with `races.location`, OpenF1 response cache under `data/openf1-cache/`).
- Data to ingest for the default run: 2024 rounds 1-11 and 24, plus 2023 rounds 1, 2, 3, 5, 6, 7, 8, 9, 16, and 22 as circuit-prior sources only.
- `docs/swap-model.md` step 3 still shows `--train 2023:1-10`; task 6.1 changes it to the new default `2024:2-11`.
