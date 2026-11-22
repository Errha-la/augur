## 1. Chart module and race trace

- [x] 1.1 Create `augur.charts` ("Chart data in one pure module") with `race_trace` and the `GET /api/races/{race_id}/trace` route for the "Race trace data" requirement ("Race trace against a reference pace"), response shape as in the design's Implementation Contract. Verify with the "Faster driver gains" example test in `backend/tests/test_charts.py` and the "No future laps" scenario plus 404 and 422 tests in `backend/tests/test_charts_api.py`.

## 2. Rejoin, stints, degradation

- [x] 2.1 Add `rejoin` and the `rejoin` route for the "Pit rejoin data" requirement ("Rejoin snapshot for the pit-stop clock"). Verify with the "Rejoin between two cars" example test (position 4, ahead D by 2.5 s) and a leader case in `backend/tests/test_charts.py`, and the "Unknown driver" and a leakage test in `backend/tests/test_charts_api.py`. [after: 1.1]
- [x] 2.2 Add `stints` and `degradation_points` with their routes for the "Stint data" and "Degradation points data" requirements ("Stints and degradation points"). Verify with the "Stint still running" and "Too few points" scenario tests in `backend/tests/test_charts.py` and leakage tests for both routes in `backend/tests/test_charts_api.py`. [after: 2.1]

## 3. Endpoints that need position-sim-calibration

- [ ] 3.1 After `position-sim-calibration` task 1.1 is on `main` ("Wave 1 backend track BE-2"), add `pit_window` and the `pit-window` route for the "Pit window data" requirement ("Pit window from the strategy simulator"). Verify with the "Agrees with the strategy table", "No window left", and "Runs out of range" scenario tests and a same-seed test in `backend/tests/test_charts_api.py`. [after: 2.2]
- [ ] 3.2 After `position-sim-calibration` task 2.4 is on `main`, add the `positions/distribution` route for the "Position distribution data" requirement and add `position_p10` and `position_p90` to `positions/history` for the "Serve position predictions" requirement ("Position distribution and fan fields"). Verify with the "Not analyzed" and "Same order as positions" scenario tests in `backend/tests/test_charts_api.py` and the updated "Response shape matches the contract" test in `backend/tests/test_positions_api.py`. [after: 3.1]

## 4. Measurement and handoff

- [ ] 4.1 Run every new endpoint against the real Abu Dhabi 2024 data at lap 1 and lap 58 with the API started from this worktree, record response times and one sample response per endpoint here, and write README notes (endpoint table rows) for `portfolio-release` under this task. Verify that the sample responses match the design's Implementation Contract field for field and the full backend suite passes. [after: 3.2]
