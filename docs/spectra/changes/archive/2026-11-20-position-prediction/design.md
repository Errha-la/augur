## Context

After `prediction-and-events`, AUGUR can predict each driver's next lap, fit the current stint's degradation, and estimate pit loss, all from `feed.laps_until(N)`. The user decided that finishing-position prediction is the headline feature (Stage 1) and that the benchmark's headline score will measure it (change `race-wrapped`). Later the same code must run on live data, so it consumes a `RaceFeed` and works one lap at a time.

## Goals / Non-Goals

**Goals:**

- At every lap N, per-driver probabilities for P1, top 3, and top 10, plus expected position, from data up to N only.
- Fast enough to precompute every lap of a race in under a minute on a laptop (estimate; measure during task 3.1).
- Reproducible results for the same data, model, and seed.

**Non-Goals:**

- Safety car, VSC, red flag, weather, retirements, and penalties; the simulation assumes a green race to the end.
- Driver-to-driver overtaking skill; passing is limited only by the dirty-air rule.
- Live data ingestion (a future `LiveFeed`).
- Strategy optimization for the whole field; each driver gets one expected pit plan.

## Decisions

### Full-field lap-by-lap simulation

For lap N the simulator runs `runs` (default 1000) independent futures for laps N+1 to `total_laps`, vectorized as arrays of shape (runs, drivers). Each simulated lap time for driver d is `base_pace_d + deg_d × (tyre_age − tyre_age_now) − fuel_gain × (lap − N) + noise`, where `base_pace_d` is the model's `predicted_next_lap_s` (fallback: the median of d's laps after lap 1, then the field median of those base paces; at lap 1, when no driver has a lap after lap 1, every driver gets the median of all lap times so far, so the order at the start decides), `deg_d` is the projected degradation described in "Projected degradation uses only trusted stint fits", `fuel_gain` is `0.03 × 110 / total_laps`, and noise is normal with d's clean-lap residual standard deviation (minimum 0.2 s). The start state is each driver's cumulative session time at lap N; lapped drivers keep their lap deficit. Seed is `seed + N` so each lap is reproducible on its own. Alternative: simulate only the remaining positions from gaps without lap times. Rejected because pit stops and tyre ageing need lap-level time.

### Projected degradation uses only trusted stint fits

`deg_d` is d's current stint slope only when the fit uses at least `POSITION_DEG_MIN_FIT_LAPS` (8) clean laps and the slope is not negative; otherwise it is the race's median slope for that compound so far, then the per-compound default from `prediction-and-events`. The result is never below 0, and the slope after a simulated stop is the next compound's median or default, also never below 0. Reason (measured 2026-11-20, Bahrain lap 15): using every fit as-is, a 5-lap fit of −0.164 s/lap projected over 42 laps gave SAR `p_win` 0.81; with this rule the lap-15 favourite is VER. Alternative: use every fit and clamp only negative slopes. Rejected because short positive fits such as 0.334 s/lap from 6 laps distort the projection the same way.

### Expected pit plan per driver

A driver who has not yet used two different dry compounds makes one more stop; others make none. The stop lap is `N + max(1, life − tyre_age) + U{−3..3}`, clipped to `[N+1, total_laps − 1]` (when that window is empty, at N = total_laps − 1, no stop is simulated), where `life` is the typical stint length SOFT 20, MEDIUM 28, HARD 38 laps (estimates; check against observed stints on the demo races). The stop adds the pit loss from `prediction-and-events` and resets tyre age; the next compound is HARD after SOFT or MEDIUM, and MEDIUM after HARD.

### Dirty-air penalty limits passing

After each simulated lap, a driver whose gap to the car ahead is below 1.0 s gets 0.4 s added to the next lap, following the PITWALL project's documented prior (dirty air 0.40 s/lap within 1.0 s). A faster car therefore passes only when its pace advantage exceeds the penalty. Alternative: a logistic overtake model. Rejected for the MVP because it needs labelled overtake data.

### Probabilities from simulated finishing order

Finishing order per run is by laps completed, then cumulative time. `p_win`, `p_podium`, `p_points` are the shares of runs finishing P1, P1-3, and P1-10; `expected_position` is the mean finishing position; `position_p10`/`position_p90` are its 10th and 90th percentiles. Results at the final lap are deterministic: the actual order with probabilities 0 or 1.

### Stage 1 backend track

This change runs in parallel with `race-dashboard`, following the Stage 1 rules in `AGENTS.md`. It starts only after `prediction-and-events` is archived (done: commit 53c1575). It runs in its own git worktree and changes only `backend/`. If any task needs a change outside `backend/`, implementation stops and this change is updated first. `spxa` reads and writes the main checkout's `docs/`, so this change's artifacts are copied into the worktree by hand, and archiving happens one change at a time. Stage 1 is finished only when this change and `race-dashboard` are both archived.

The frontend track mocks `/positions` and `/positions/history` from the API contract below until this change serves them, so that contract is fixed: field names, nesting, and ordering do not change without updating both changes. Alternative: let the frontend mock its own guess and reconcile at the end. Rejected because a mismatch would only show up when the mocks are removed, just before archiving `race-dashboard`.

### Precompute per lap during analysis

`python -m augur.analyze` also runs the simulator at each lap it steps and replaces the race's rows for that model in `position_predictions(race_id, model, lap, code, p_win, p_podium, p_points, expected_position, position_p10, position_p90, runs, seed)`. `runs` and `seed` are stored per row because the API reports them and `python -m augur.analyze --runs` can change the run count. The API reads the table.

## Implementation Contract

**API**

- `GET /api/races/{race_id}/positions?lap=N` → `{race_id, lap, model, analyzed, runs, seed, drivers: [{code, p_win, p_podium, p_points, expected_position, position_p10, position_p90}]}` with `drivers` ordered by `expected_position`; same 404/422 rules as other replay endpoints. `analyzed` is always present: `true` when the race has predictions for the `AUGUR_MODEL` model, otherwise `false` with empty `drivers` and `runs`/`seed` set to `null`.
- `GET /api/races/{race_id}/positions/history?lap=N` → `{race_id, model, analyzed, laps: [{lap, drivers: [{code, p_win, p_podium, expected_position}]}]}` for laps 1 to N only, in ascending lap order; `analyzed: false` with empty `laps` when the race has no predictions for the model.
- These shapes are the source for the `race-dashboard` mocks (see Stage 1 backend track).

**Acceptance**

- `pytest backend` covers probability sums, determinism, the dominant-leader case, the dirty-air rule, the pit plan, and future-lap independence.
- Manual: analyze `2024-01-bahrain-grand-prix`, record the time analysis takes, and record at laps 15, 29, and 43 the three drivers with the highest `p_podium` next to the actual podium. The numbers are recorded in this change's task notes, not in the root `README.md` (outside `backend/`).
- Contract check: a real response from each endpoint for an analyzed race has exactly the field names and nesting listed above.

**Scope**

- In: simulator, pit plan, dirty-air rule, storage, two endpoints, analyze integration; files under `backend/` only.
- Out: frontend display and mocks (change `race-dashboard`), the root `README.md` and any other path outside `backend/`, scoring and benchmark (change `race-wrapped`), safety car modelling, live data.

## Risks / Trade-offs

- [Green-race assumption overstates certainty when a safety car is likely] → stated in the dashboard tooltip and README; safety car risk is a later feature.
- [Pit plan and stint lengths are estimates] → constants in `augur.config`; compare predicted and actual stop laps on the demo races.
- [Runtime of 1000 runs × every lap] → vectorized with NumPy; if precompute exceeds the estimate, lower runs per lap and record the number.

## Open Questions

- Where the measured results from task 3.1 go in the root `README.md` "Model results" section. This track may not edit `README.md`, so the numbers stay in tasks.md until the user decides who adds the README lines (for example, on `main` after this change is merged, or in change `polish`).
