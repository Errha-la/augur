## 1. Chart module and race trace

- [x] 1.1 Create `augur.charts` ("Chart data in one pure module") with `race_trace` and the `GET /api/races/{race_id}/trace` route for the "Race trace data" requirement ("Race trace against a reference pace"), response shape as in the design's Implementation Contract. Verify with the "Faster driver gains" example test in `backend/tests/test_charts.py` and the "No future laps" scenario plus 404 and 422 tests in `backend/tests/test_charts_api.py`.

## 2. Rejoin, stints, degradation

- [x] 2.1 Add `rejoin` and the `rejoin` route for the "Pit rejoin data" requirement ("Rejoin snapshot for the pit-stop clock"). Verify with the "Rejoin between two cars" example test (position 4, ahead D by 2.5 s) and a leader case in `backend/tests/test_charts.py`, and the "Unknown driver" and a leakage test in `backend/tests/test_charts_api.py`. [after: 1.1]
- [x] 2.2 Add `stints` and `degradation_points` with their routes for the "Stint data" and "Degradation points data" requirements ("Stints and degradation points"). Verify with the "Stint still running" and "Too few points" scenario tests in `backend/tests/test_charts.py` and leakage tests for both routes in `backend/tests/test_charts_api.py`. [after: 2.1]

## 3. Endpoints that need position-sim-calibration

- [x] 3.1 After `position-sim-calibration` task 1.1 is on `main` ("Wave 1 backend track BE-2"), add `pit_window` and the `pit-window` route for the "Pit window data" requirement ("Pit window from the strategy simulator"). Verify with the "Agrees with the strategy table", "No window left", and "Runs out of range" scenario tests and a same-seed test in `backend/tests/test_charts_api.py`. [after: 2.2]
- [x] 3.2 After `position-sim-calibration` task 2.4 is on `main`, add the `positions/distribution` route for the "Position distribution data" requirement and add `position_p10` and `position_p90` to `positions/history` for the "Serve position predictions" requirement ("Position distribution and fan fields"). Verify with the "Not analyzed" and "Same order as positions" scenario tests in `backend/tests/test_charts_api.py` and the updated "Response shape matches the contract" test in `backend/tests/test_positions_api.py`. [after: 3.1]

## 4. Measurement and handoff

- [x] 4.1 Run every new endpoint against the real Abu Dhabi 2024 data at lap 1 and lap 58 with the API started from this worktree, record response times and one sample response per endpoint here, and write README notes (endpoint table rows) for `portfolio-release` under this task. Verify that the sample responses match the design's Implementation Contract field for field and the full backend suite passes. [after: 3.2]

  **4.1 results (2026-11-23).** API started from this worktree (`uvicorn augur.api:app --port 8077`, `AUGUR_DATA_DIR` = main `data/`, `AUGUR_MODEL` default `lightgbm`), race `2024-24-abu-dhabi-grand-prix`, driver NOR, defaults `runs=1000 seed=42`. Best of 3 warm requests (localhost):

  | Endpoint | lap 1 | lap 58 | Notes |
  |---|---|---|---|
  | `trace` | 9 ms | 11 ms | 20 drivers, 58 points each at lap 58 |
  | `rejoin` | 33 ms | 42 ms | 19 / 16 cars with a gap |
  | `pit-window` | 51 ms | 68 ms | both empty (lap 1: no driver state, same as `strategy`; lap 58: no lap left). Lap 5: 51 plans in ~50 ms; lap 20: 36 plans in ~60 ms. Well under the 2 s estimate. |
  | `stints` | 10 ms | 14 ms | |
  | `degradation` | 7 ms | 10 ms | lap 1: no compounds (no clean lap yet); lap 58: SOFT, MEDIUM, HARD (56 KB) |
  | `positions/distribution` | 2 ms | 2 ms | 20 drivers, 20 shares each |
  | `positions/history` | 2 ms | 5 ms | 127 KB at lap 58 |

  All 18 sample responses (lap 1, lap 58, plus pit-window at laps 2, 3, 5, 20) were checked field for field against the Implementation Contract: no extra or missing fields. Full backend suite: 467 passed, 1 skipped.

  Sample responses (lists trimmed):
  - `trace`: `{"race_id": "2024-24-abu-dhabi-grand-prix", "lap": 58, "reference_lap_s": 90.993, "drivers": [{"code": "NOR", "team_color": "#FF8000", "points": [{"lap": 1, "delta_s": -0.586}, {"lap": 2, "delta_s": -17.941}]}]}`
  - `rejoin`: `{"race_id": "2024-24-abu-dhabi-grand-prix", "lap": 58, "driver": "NOR", "pit_loss_s": 22.86, "lap_length_s": 88.325, "cars": [{"code": "NOR", "position": 1, "gap_to_leader_s": 0.0, "laps_behind_leader": 0}, {"code": "SAI", "position": 2, "gap_to_leader_s": 5.844, "laps_behind_leader": 0}], "rejoin": {"position": 2, "gap_to_leader_s": 22.86, "ahead": "SAI", "ahead_gap_s": 17.016, "behind": "LEC", "behind_gap_s": 9.119}}`
  - `pit-window` (lap 20): `{"race_id": "2024-24-abu-dhabi-grand-prix", "lap": 20, "driver": "NOR", "runs": 1000, "seed": 42, "pit_loss_s": 22.604, "best_pit_lap": 32, "plans": [{"pit_lap": 21, "mean_s": 3375.672, "p10_s": 3356.981, "p90_s": 3393.992, "delta_s": 6.214}, {"pit_lap": 22, "mean_s": 3374.55, "p10_s": 3356.761, "p90_s": 3391.771, "delta_s": 5.092}]}`
  - `stints`: `{"race_id": "2024-24-abu-dhabi-grand-prix", "lap": 58, "drivers": [{"code": "NOR", "stints": [{"stint": 1, "compound": "MEDIUM", "start_lap": 1, "end_lap": 26, "start_tyre_age": 1}, {"stint": 2, "compound": "HARD", "start_lap": 27, "end_lap": 58, "start_tyre_age": 1}]}]}`
  - `degradation`: `{"race_id": "2024-24-abu-dhabi-grand-prix", "lap": 58, "compounds": [{"compound": "SOFT", "fit": {"slope_s_per_lap": 0.179, "intercept_s": 89.602, "n": 24}, "points": [{"code": "MAG", "lap": 32, "tyre_age": 2, "fuel_corrected_s": 88.999}]}]}`
  - `positions/distribution`: `{"race_id": "2024-24-abu-dhabi-grand-prix", "lap": 58, "model": "lightgbm", "analyzed": true, "drivers": [{"code": "NOR", "position_distribution": [1.0, 0.0, 0.0]}]}`
  - `positions/history` (one driver entry): `{"code": "NOR", "p_win": 1.0, "p_podium": 1.0, "expected_position": 1.0, "position_p10": 1.0, "position_p90": 1.0}`

  **README notes for `portfolio-release`** (endpoint table rows; all take `lap=N` and read only laps up to N):

  | Endpoint | Returns |
  |---|---|
  | `GET /api/races/{race_id}/trace?lap=N` | Race trace: each driver's time gained or lost against a reference lap pace, per lap |
  | `GET /api/races/{race_id}/rejoin?lap=N&driver=D` | Pit-stop clock: gaps to the leader and where D would rejoin if it pitted now (snapshot; other cars assumed not to pit) |
  | `GET /api/races/{race_id}/pit-window?lap=N&driver=D[&runs&seed]` | Simulated remaining race time for a stop on every remaining lap (same simulator as `strategy`), best pit lap |
  | `GET /api/races/{race_id}/stints?lap=N` | Tyre stints so far per driver |
  | `GET /api/races/{race_id}/degradation?lap=N` | Fuel-corrected clean laps by tyre age per dry compound, with a fitted line |
  | `GET /api/races/{race_id}/positions/distribution?lap=N` | Finishing-position probabilities P1..Pn per driver |
  | `GET /api/races/{race_id}/positions/history?lap=N` | (existing) now also `position_p10` / `position_p90` per driver for the position fan |
