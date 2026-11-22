## Context

The dashboard today has a timing list, an event panel, a focus panel with a strategy table, and one lap chart. Stage 4 adds strategy charts (`strategy-chart-widgets`, Wave 2). Those widgets need data shapes that are fixed now, so the frontend track can mock them while this backend track builds them. Existing endpoints (`state`, `laps`, `predictions`, `events`, `positions`, `positions/history`, `strategy`) stay as they are except two additive fields in `positions/history`.

This is the BE-2 track of Stage 4 Wave 1 (`AGENTS.md`): own worktree, `backend/` only, a new chart-data module and its routes; no change to simulator, degradation, or strategy internals. It calls `strategy.simulate_pit_laps()` and reads the stored `position_distribution`, both added by `position-sim-calibration` (BE-1).

## Goals / Non-Goals

**Goals:**

- Serve chart data for the race trace, pit-stop clock (rejoin), pit-window curve, tyre stints, degradation by compound, position fan, and position heatmap.
- Every response at lap N reads only laps up to N, with a leakage test per endpoint.
- Fix the response shapes in this design so `strategy-chart-widgets` can mock them.

**Non-Goals:**

- No frontend code; `strategy-chart-widgets` renders these.
- No new model, simulator rule, or stored table. The pit window reuses the strategy simulator; the distribution is stored by `position-sim-calibration`.
- No projected future stints or projected race trace beyond lap N; projections stay in `positions`, `strategy`, and `pit-window`.
- No caching layer: each endpoint computes from laps up to N per request (measured cost to be recorded in tasks.md).
- No README edit; notes go to tasks.md for `portfolio-release`.

## Decisions

### Chart data in one pure module

`augur.charts` holds pure functions that take laps already cut at lap N (plus race metadata) and return plain dicts: `race_trace`, `rejoin`, `stints`, `degradation_points`, `pit_window`. Routes in `augur.api` only validate input, open the feed with `feed.laps_until(N)`, and call them. Reason: the same pattern as `positions` and `strategy`, and pure functions are easy to test for leakage. Alternative: compute inside route handlers. Rejected because the leakage tests would then need the HTTP layer.

### Race trace against a reference pace

Race time of driver d at lap j is `session_time_s(d, j) − race_start_s`, where `race_start_s` is the median over drivers of `session_time_s − lap_time_s` on lap 1 (drivers without a lap-1 time are skipped). `reference_lap_s` is the median, over drivers with at least one completed lap by N, of race time at their last completed lap divided by that lap number. Each point is `delta_s = reference_lap_s × j − race_time(d, j)`, rounded to 3 decimals: positive means ahead of the reference. Laps without a session time are omitted. The reference is recomputed at every N from laps up to N only, so the whole curve can shift slightly as N grows. Alternative: reference from the winner's average. Rejected because the winner is future information.

### Rejoin snapshot for the pit-stop clock

`rejoin` uses `race_state` at lap N: each car's `position`, `gap_to_leader_s` (real time behind the leader at the car's own lap count) and `laps_behind_leader`. `pit_loss_s` is `strategy.pit_loss` of laps up to N, fallback 22.0 s. `lap_length_s` (the clock's full circle) is the leader's last lap time when it is a clean lap, else the median of the leader's clean laps up to N, else the median of all lap times up to N. D's projected gap is `gap_to_leader_s(D) + pit_loss_s`; the rejoin position is 1 plus the number of other cars with a gap at or below it; `ahead` and `behind` are the nearest such cars with their gap differences. When D leads, D's gap is 0. It is a snapshot: other cars are assumed not to pit on that lap. `rejoin` is null when D has no completed lap or no gap at N.

### Pit window from the strategy simulator

`pit_window` calls `strategy.simulate_pit_laps` for every pit lap from N+1 to `total_laps − 2`, plus `None` ("no further stop") only when D has used two dry compounds, with `runs` (default 1000, 100–5000) and `seed` (default 42). `delta_s` is each plan's `mean_s` minus the lowest `mean_s`; `best_pit_lap` is the pit lap with the lowest `mean_s` (null when the best plan is no stop or there are no plans). Reason: the chart then agrees with the strategy table for the same pit lap. Alternative: a closed-form expected-time curve. Rejected because it would drift from the strategy model.

### Stints and degradation points

`stints` lists each driver's stints with laps up to N: `stint`, `compound`, `start_lap`, `end_lap` (the last lap at or before N), `start_tyre_age` (tyre life on the stint's first lap), ordered by running order at N. `degradation_points` lists clean laps up to N (`clean_mask`) with `code`, `lap`, `tyre_age`, `fuel_corrected_s` (`features.fuel_corrected`) per dry compound, and a least-squares `fit` (`slope_s_per_lap`, `intercept_s`, `n`) through that compound's points, null below 4 points. The fit describes the plotted points only; it is not the simulator's guarded slope. Alternative: serve the simulator's slope. Rejected because it would couple this track to BE-1 internals and the chart would show a line that does not match its dots.

### Position distribution and fan fields

`positions/distribution?lap=N` returns the stored `position_distribution` for lap N for the `AUGUR_MODEL` model, in the same driver order as `positions`, with `analyzed` false and empty `drivers` when the race has no predictions, and null `position_distribution` for rows stored before the column existed. `positions/history` adds `position_p10` and `position_p90` to each driver entry; all other fields stay. Reason: a separate endpoint keeps the `positions` contract unchanged, and the history additions are the only data the fan needs.

### Wave 1 backend track BE-2

This change follows the Stage 4 Wave 1 rules in `AGENTS.md`: own worktree, `backend/` only. Tasks 3.1 (pit window) and 3.2 (distribution) start only after `position-sim-calibration` tasks 1.1 and 2.4 are on `main`; the other tasks start immediately. The response shapes in the Implementation Contract are fixed: `strategy-chart-widgets` mocks them, so a change to field names, nesting, or ordering updates both changes first.

## Implementation Contract

All endpoints: unknown race → 404 `race not found`; lap outside 1..total_laps → 422 (same validation as `state`); unknown driver where a driver is required → 404 `driver not found`; `runs` outside 100–5000 → 422. Numbers rounded to 3 decimals unless stated. No response reads laps after N; a test per endpoint alters laps after N and asserts an identical response.

```json
GET /api/races/{race_id}/trace?lap=N
{"race_id": "...", "lap": N, "reference_lap_s": 88.123,
 "drivers": [{"code": "NOR", "team_color": "#ff8000", "points": [{"lap": 1, "delta_s": 2.345}]}]}
// drivers in running order at N; points ascending by lap, laps 1..min(N, laps completed)

GET /api/races/{race_id}/rejoin?lap=N&driver=D
{"race_id": "...", "lap": N, "driver": "D", "pit_loss_s": 21.5, "lap_length_s": 87.9,
 "cars": [{"code": "NOR", "position": 1, "gap_to_leader_s": 0.0, "laps_behind_leader": 0}],
 "rejoin": {"position": 7, "gap_to_leader_s": 34.2, "ahead": "RUS", "ahead_gap_s": 1.1, "behind": "HAM", "behind_gap_s": 0.6}}
// cars in running order, cars without a gap omitted; rejoin null when D has no gap; ahead/behind and their gaps null at the ends

GET /api/races/{race_id}/pit-window?lap=N&driver=D[&runs=1000&seed=42]
{"race_id": "...", "lap": N, "driver": "D", "runs": 1000, "seed": 42, "pit_loss_s": 21.5,
 "best_pit_lap": 34,
 "plans": [{"pit_lap": 30, "mean_s": 2550.1, "p10_s": 2547.0, "p90_s": 2553.4, "delta_s": 1.2}]}
// plans ascending by pit_lap, with the no-stop plan (pit_lap null) last when offered; empty when no window or no driver state

GET /api/races/{race_id}/stints?lap=N
{"race_id": "...", "lap": N,
 "drivers": [{"code": "NOR", "stints": [{"stint": 1, "compound": "MEDIUM", "start_lap": 1, "end_lap": 25, "start_tyre_age": 1}]}]}

GET /api/races/{race_id}/degradation?lap=N
{"race_id": "...", "lap": N,
 "compounds": [{"compound": "MEDIUM", "fit": {"slope_s_per_lap": 0.061, "intercept_s": 89.2, "n": 140},
   "points": [{"code": "NOR", "lap": 5, "tyre_age": 5, "fuel_corrected_s": 89.5}]}]}
// compounds in SOFT, MEDIUM, HARD order, only those with at least one point; fit null below 4 points

GET /api/races/{race_id}/positions/distribution?lap=N
{"race_id": "...", "lap": N, "model": "lightgbm", "analyzed": true,
 "drivers": [{"code": "NOR", "position_distribution": [0.61, 0.22, 0.1]}]}

GET /api/races/{race_id}/positions/history?lap=N   (existing; per driver entry adds two fields)
{"code": "NOR", "p_win": 0.6, "p_podium": 0.9, "expected_position": 1.6, "position_p10": 1.0, "position_p90": 3.0}
```

**Acceptance**: tests named in tasks.md pass; the existing `positions/history` shape test is updated to the new field list; each endpoint's response time on Abu Dhabi lap 58 is measured and recorded in tasks.md (`pit-window` at 1000 runs is expected to be the slowest; estimate under 2 s, to be confirmed by that measurement).

**Scope**: In: `augur.charts`, routes in `augur.api`, tests. Out: simulator and strategy internals, stored tables, frontend, README.

## Risks / Trade-offs

- [Pit-window latency with up to about 55 plans × 1000 runs] → Measure on Abu Dhabi lap 1 and lap 58; if above 2 s at lap 1, the default stays 1000 and tasks.md records the time, and `strategy-chart-widgets` requests it on the same schedule as the strategy table.
- [Race start time from lap-1 session times is approximate] → The trace shows differences between drivers, which do not depend on the start offset; only the absolute level shifts.
- [Rejoin ignores other cars pitting the same lap] → Labelled as a snapshot in the response contract; the frontend states it.
- [BE-1 slips and blocks tasks 3.1 and 3.2] → All other tasks are independent; the frontend mocks keep Wave 2 unblocked.
