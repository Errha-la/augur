## Context

`race-data-replay` provides normalized laps in Parquet, a SQLite catalog (including `races.location`), the OpenF1 ingest command, and `ReplayStore.laps_until(race_id, lap)` as the only cutoff-safe read path. OpenF1 is the only data source. It has race sessions from 2023 onward only: `sessions?year=2022&session_name=Race` returns `No results found` (measured 2026-11-19). `track_status` and `is_accurate` are derived by the normalizer (see the `race-data-ingest` spec), so `is_accurate` already means "lap time present, lap > 1, not a pit-in or pit-out lap"; compound `UNKNOWN` is stored as null. This change adds the "Why" and "What next" layers. The build window is two days, so every model is small, deterministic, and explainable. All numeric thresholds below are estimates chosen for the MVP, named as constants in `augur.config`, and listed in the risks section.

## Goals / Non-Goals

**Goals:**

- A lap-time model whose test error is reported honestly next to a baseline.
- Degradation, strategy, and events computed at lap N from laps up to N only.
- Every event answers What happened / Why / What next in plain sentences with the numbers behind them.
- Events for a demo race precomputed once, so the dashboard reads them instantly.

**Non-Goals:**

- Overtake probability and final position prediction (change `position-prediction`), safety car risk.
- The `overcut_window` detector (change `polish`, Stage 3).
- Driver identity as a model feature (too little data per driver; the driver's own recent pace already carries driver skill).
- "Emerging strategic advantage" as a separate event type; strategy output is attached to degradation and undercut events instead.
- LLM-generated text (change `llm-commentary`).
- Wet-race handling; intermediate and wet laps are excluded from clean laps.
- Hyperparameter search; LightGBM uses fixed parameters.

## Decisions

### Clean-lap filter and fuel correction

A clean lap has `lap_time_s` present, `lap > 1`, `pit_in` and `pit_out` false, `track_status == "1"` (green), `is_accurate` true, compound in SOFT/MEDIUM/HARD, and `lap_time_s` no more than 10% slower than the fastest clean lap in the race up to that point (`OUTLIER_PCT = 10`). Fuel-corrected time is `lap_time_s + FUEL_S_PER_LAP * (lap - 1)` with `FUEL_S_PER_LAP = 0.03 s/kg * 110 kg / total_laps` (about 0.058 s for a 57-lap race). Both the clean-lap rule and the fuel formula follow the open-source Armchair-Strategist project (`f1_visualization/preprocess.py`); PITWALL documents a similar 0.035 s/lap prior. These are estimates. Alternative: no fuel correction. Rejected because fuel burn hides tyre degradation in raw lap times.

### Lap-time model predicts delta from recent pace

The target is the next clean lap time minus the driver's median of their last 3 clean laps (`recent_pace_s`). Features: `tyre_life`, `stint`, `compound`, `lap_fraction` (lap / total_laps), `laps_since_pit`, `recent_pace_trend_s` (last clean lap minus `recent_pace_s`), `circuit_deg_prior_s`, `team_pace_gap_s` (see Circuit priors and team pace, no driver identity). The prediction is `recent_pace_s + predicted_delta`. Features for predicting lap k use only rows with lap < k. Alternative: predicting absolute lap time. Rejected because absolute times differ by circuit and would not transfer from the training circuits to the test circuits.

### Circuit priors and team pace, no driver identity

Recent pace already captures how fast this driver, car, and circuit are today; what it misses is how the delta evolves at this circuit and for this car. Two features add that:

- `circuit_deg_prior_s`: the median stint degradation (`deg_s_per_lap`) for the current compound in the most recent earlier season's race at the same `location`; null when that race is not ingested. Every race in the default train and test sets is a 2024 race, so the prior comes from 2023. The 2023 races below are ingested as prior sources only and are never training or test races. Location strings are identical across the two seasons (measured from OpenF1 `sessions` on 2026-11-19).

| 2024 round (location) | Role | 2023 prior race |
|---|---|---|
| 1 Sakhir | test | round 1 |
| 2 Jeddah | train | round 2 |
| 3 Melbourne | train | round 3 |
| 4 Suzuka | train | round 16 |
| 5 Shanghai | train | none (prior null) |
| 6 Miami | train | round 5 |
| 7 Imola | train | none, 2023 race cancelled (prior null) |
| 8 Monaco | train | round 6 |
| 9 Montréal | train | round 8 |
| 10 Barcelona | train | round 7 |
| 11 Spielberg | train | round 9 |
| 24 Yas Island | test | round 22 |

**Supersedes:** the earlier plan to take 2023 training-race priors from 2022 races. OpenF1 has no 2022 race sessions, so that prior could not exist for any training row and the model would never learn from it. Replaced by "Train on 2024 rounds 2-11, test on held-out 2024 races" below.
- `team_pace_gap_s`: the median of the team's clean laps over the 5 laps before lap k minus the median of all clean laps in the same window.

Driver identity is not a feature: 10 races × 20 drivers is too little data and the model would memorize drivers. Alternative: a circuit one-hot. Rejected because each circuit appears once per season and would not generalize.

### Pluggable lap-time models

AUGUR is meant to be cloned and improved locally, so the model is behind a `LapTimeModel` protocol: attributes `name` and `author`, methods `fit(features, target)`, `predict(features)`, `save(path)`, and `load(path)`. A registry in `augur.models.registry` maps a name to a class. Built-in models: `lightgbm` (author `AUGUR`) and `baseline` (delta 0). Commands and the API take the model name; files are stored per model as `data/models/<name>.joblib` and `data/models/<name>_metrics.json`. The API uses the model named by environment variable `AUGUR_MODEL`, default `lightgbm`. Alternative: one hard-coded LightGBM model. Rejected because swapping models later would change every command and table.

### Train on 2024 rounds 2-11, test on held-out 2024 races

Default training races are 2024 rounds 2-11 and the default test races are 2024 rounds 1 and 24 (the two demo races, also the fixed benchmark races); both are set with `--train` and `--test` options in the form `<year>:<rounds>` (for example `2024:2-11`, `2024:1,24`). Training on the same season as the test races keeps cars and regulations the same and lets the 2023 circuit prior be non-null in both sets. Trade-off: training races 2-11 happen after test race 1 in time, so the model has seen 2024 car behaviour from later in the season; no lap of a test race is used, and the README states this next to the MAE numbers. Two training races (Shanghai, Imola) have a null prior, so the model also sees null priors.

**Supersedes:** "Train on 2023, test on held-out 2024 races" (default `--train 2023:1-10`). Alternatives considered: keep 2023 training and drop `circuit_deg_prior_s`, or keep it with all training rows null; rejected because the feature would carry no information. The baseline predicts delta 0 (next lap equals recent pace). Metrics report MAE in seconds for model and baseline on clean test laps. No minimum MAE is required; the README reports the numbers as measured.

### Linear stint degradation with cliff check

For each driver's current stint, fit a least-squares line of fuel-corrected time against `tyre_life` over clean laps up to lap N, requiring at least `MIN_STINT_LAPS = 4`. The slope is `deg_s_per_lap`. A cliff is flagged when the stint has at least 6 clean laps and both of the last 2 clean laps are more than `CLIFF_RESIDUAL_S = 0.8` s slower than the line fitted on the earlier clean laps.

### Seeded Monte Carlo strategy simulation

Candidates for a driver at lap N: "no further stop" (only when the driver has already used two different dry compounds), and "pit on lap N+k" for k in {1, 3, 5, 8} while N+k < total_laps - 1. Each simulated lap time is `base_pace + deg * tyre_age + noise`; pitting resets tyre age, uses the race-wide median degradation of the next compound observed up to lap N (fallback per compound: SOFT 0.085, MEDIUM 0.050, HARD 0.028 s/lap; illustrative values seen in public hobby projects, unverified), and adds a pit loss. Pit loss is the median observed pit cost up to lap N (in-lap plus out-lap minus two times that driver's recent pace), fallback 22.0 s (estimate; PITWALL documents per-circuit medians such as Monza about 21 s and Monaco about 24 s). Noise is normal with the driver's clean-lap residual standard deviation, minimum 0.2 s. Default 1000 runs, seed 42, so results are reproducible. Alternative: a deterministic single-pass comparison. Rejected because the spread (p10/p90, win probability) is what makes the strategy comparison explainable.

### Rule-based event detectors

Each detector is a pure function of the laps up to lap N, the predictions at lap N, and the degradation fits at lap N. Rules and severity:

| Type | Fires when | Severity score |
|---|---|---|
| `pace_drop` | clean lap N is more than `PACE_DROP_S = 1.0` s slower than its prediction; at most once per driver per 3 laps | min(100, 30 × seconds slower than predicted) |
| `degradation_warning` | stint `deg_s_per_lap` ≥ 0.10 with ≥ 8 clean laps (`DEG_WARNING_MIN_LAPS`), or a cliff; once per driver per stint (a cliff can fire once more) | cliff 80, otherwise min(100, 500 × slope) |
| `undercut_window` | chaser within 2.5 s of the car ahead on the same lap count, car ahead tyre age ≥ 12, neither pitted in the last 3 laps; once per pair per stint of the car ahead | 60 |
| `position_change` | a driver gains or loses ≥ 2 places from lap N-1 to N, or the leader changes (score 90); not on lap 1; not for a driver whose own lap N is a pit-in or pit-out lap (a leader change is skipped when the new leader pitted on lap N) | min(100, 20 × places) |

### Event thresholds tuned on the demo races

Measured on 2026-11-19 with `lightgbm` before tuning: 2024 Bahrain had 201 events (58 `degradation_warning`, 76 `position_change`) and 2024 Abu Dhabi 145 (37 and 43). Of the degradation warnings, 32 (Bahrain) and 21 (Abu Dhabi) fired at exactly 5 clean laps, the earliest the rule allowed, where a 5-point line fit is noisy (example: RIC, 6-lap-old HARD tyres, 0.366 s/lap, "pitting on lap 20 in 93% of simulations"). Every `position_change` fell on a lap with pit activity, and 39 (Bahrain) and 24 (Abu Dhabi) were the driver's own pit stop.

**Supersedes:** `degradation_warning` with ≥ 5 clean laps → ≥ 8 clean laps; and `position_change` for every driver → not for a driver who pitted on that lap (their own in-lap or out-lap). Position changes caused by other cars' stops still fire. Alternatives considered: drop every `position_change` on a lap with any pit stop (rejected: it would remove all of them on the demo races, measured), and keep all of them for the dashboard to filter (rejected by the user on 2026-11-19). The before/after counts per type are recorded in the README.

### Analysis bookkeeping, error labels, and simulated tyre choice

Three details decided during implementation:

- `augur.analyze` also writes an `analyses(race_id, model, n_events, analyzed_at)` row. The `events` table alone cannot tell "analyzed with zero events" from "never analyzed", and the events endpoint must report `analyzed` true for the first.
- A race that is not ingested has no known event-name slug, so `augur.train` names it by its race_id prefix `<year>-<rr>` (for example `missing race 2024-05, run augur.ingest first`); an ingested race is named by its full race_id.
- A simulated pit stop fits HARD, or MEDIUM when the driver is already on HARD (an unknown compound also gets HARD). The design did not fix the compound; this keeps candidates comparable with one rule.

### Deterministic What / Why / Next analysis

Each event carries `analysis.what`, `analysis.why`, `analysis.next` built from fixed templates per type, filled with the evidence values. The voice is an analyst explaining to fans: `next` is a probabilistic outlook ("Pitting on lap 21 is NOR's fastest option in 62% of simulations"), never an instruction ("Pit now"). `degradation_warning` and `undercut_window` events add the best strategy from the Monte Carlo simulation for the affected driver to `next`. No LLM is used.

### Incremental event engine on a race feed

`augur.events.EventEngine(feed, model)` keeps detector state (dedupe memory, previous positions) and exposes `step(lap)`, which reads `feed.laps_until(lap)`, computes predictions and fits for that lap, runs the detectors, and returns the new events. Laps must be stepped in order. The replay precompute loops `step(1..total_laps)` over a `ReplayFeed`; a future live service calls `step` each time `feed.latest_lap()` increases. Alternative: a batch function over the whole race. Rejected because it cannot run on live data.

### Precompute events per race into SQLite

`python -m augur.analyze --race <race_id> [--model lightgbm]` steps an `EventEngine` over a `ReplayFeed` from lap 1 to total_laps, and replaces that race's rows for that model in the `events` table (`events` has a `model` column). The command refuses (exit 1) to analyze a race that is in the model's training set. The API then reads events with `lap <= N`. Alternative: detect on each request. Rejected because it repeats all earlier laps for every request.

## Implementation Contract

**Commands**

- `python -m augur.train [--model lightgbm] [--train 2024:2-11] [--test 2024:1,24]` → writes `data/models/<model>.joblib` and `data/models/<model>_metrics.json` = `{model, author, train_races, test_races, n_train, n_test, mae_model_s, mae_baseline_s, trained_at}`; prints both MAE values. Exits 1 with `missing race <race_id>, run augur.ingest first` when a listed race is not ingested, with `unknown model <name>` for a name not in the registry, and with `train and test races overlap: <race_id>` when a race is in both sets.
- `python -m augur.analyze --race <race_id> [--model lightgbm]` → replaces the race's rows for that model in `events` and upserts its `analyses` row; prints `analyzed <race_id>: <n> events`; exit 1 when the model file is missing (`model <name> is not trained, run augur.train first`), the model is unknown, or the race is in the training set (`race <race_id> is in the training set of model <name>`).

**HTTP API** (added to `augur.api:app`; same 404/422 rules as `race-data-replay`)

- `GET /api/races/{race_id}/predictions?lap=N` → `{race_id, lap, drivers: [{code, predicted_next_lap_s, recent_pace_s, deg_s_per_lap, deg_laps, cliff}]}`; fields are `null` when there is not enough clean data.
- `GET /api/races/{race_id}/strategy?lap=N&driver=CODE[&runs=1000&seed=42]` → `{race_id, lap, driver, runs, seed, pit_loss_s, strategies: [{name, pit_lap, mean_s, p10_s, p90_s, win_probability}]}` ordered by `mean_s`; `runs` between 100 and 5000, else 422.
- `GET /api/races/{race_id}/events?lap=N` → `{race_id, lap, model, analyzed, events: [...]}` for the model named by `AUGUR_MODEL` with `lap <= N`, ordered by lap descending then severity descending. Each event: `{id, lap, type, drivers, severity, title, analysis: {what, why, next}, evidence}`. `id` is `<race_id>:<lap>:<type>:<drivers joined by "-">`. When the race has not been analyzed, `analyzed` is false and `events` is empty.

**Acceptance**

- `pytest backend` passes offline using the synthetic fixtures plus small hand-built stints.
- `test_events_unaffected_by_future_laps` and `test_predictions_unaffected_by_future_laps` alter rows with lap > N and assert identical output at lap N.
- Manual: train with defaults, analyze `2024-01-bahrain-grand-prix` and `2024-24-abu-dhabi-grand-prix`, and confirm each has at least one event of type `degradation_warning`.

**Scope**

- In: features, the `LapTimeModel` protocol and registry with two built-in models, degradation, simulator, `EventEngine` with four detectors, templates, two commands, three endpoints, README metrics section.
- Out: frontend, event outcomes and benchmark scoring (change `race-wrapped`), new event types, model tuning, `LiveFeed`, changes to the OpenF1 ingest or normalized lap schema.

## Risks / Trade-offs

- [Thresholds (fuel 0.03 s/kg × 110 kg, 10% outlier rule, pace drop 1.0 s, cliff 0.8 s, undercut 2.5 s, pit loss fallback 22 s, per-compound degradation fallbacks) are estimates] → kept as named constants in `augur.config`; event counts per type were measured on both demo races and two rules tuned (see Event thresholds tuned on the demo races). The other thresholds stay untuned estimates.
- [Model may barely beat the baseline] → report both MAEs honestly; the dashboard still works on the baseline-relative residuals.
- [Downloading 22 races (12 from 2024, 10 prior sources from 2023) is slow; not measured] → OpenF1 responses are cached under `data/openf1-cache/`, so each race is downloaded once; `--train` accepts fewer rounds. Task 6.1 records the actual ingest time.
- [Training races come after test race 1 in the same season] → no test-race lap is used; the README states the split and the trade-off.
- [Safety car laps distort pace] → excluded by the clean-lap filter; position changes under safety car still fire.
