## Purpose

Give viewers, at any lap, the probability that each driver wins, reaches the podium, or scores points, by simulating the rest of the race for the whole field from data available up to that lap.

## ADDED Requirements

### Requirement: Simulate the remaining race for every driver

For lap N the system SHALL simulate laps N+1 to `total_laps` for all drivers `runs` times (default 1000) with seed `seed + N` (default seed 42), starting from each driver's cumulative time and laps completed at lap N, using predicted pace, stint degradation, fuel gain, normal noise, the expected pit plan, and the dirty-air penalty. It SHALL read race data only through `feed.laps_until(N)`. The projected degradation SHALL use a driver's own stint slope only when the fit has at least 8 clean laps and a non-negative slope, otherwise the race's compound median or the per-compound default, and SHALL never be negative.

#### Scenario: Dominant leader

- **WHEN** the leader is 30 s ahead of P2 with 3 laps left and both have similar pace
- **THEN** the leader's `p_win` is at least 0.95

#### Scenario: Deterministic per lap

- **WHEN** predictions for lap 20 are computed twice with the same data, model, and seed
- **THEN** both results are identical

#### Scenario: Short or negative stint fit

- **WHEN** a driver's current stint fit has a slope of −0.164 s/lap, or a slope of 0.334 s/lap from 5 clean laps, and the race's median slope for that compound is 0.05 s/lap
- **THEN** the projected degradation for that driver is 0.05 s/lap

#### Scenario: Altered future laps

- **WHEN** rows with lap greater than 20 are altered and predictions for lap 20 are computed again
- **THEN** the results are identical to the original

### Requirement: Expected pit plan

A driver who has not used two different dry compounds by lap N SHALL make exactly one simulated stop when N < total_laps − 1, and no stop when N = total_laps − 1 because the stop window is empty, on lap `N + max(1, life − tyre_age) + U{−3..3}` clipped to `[N+1, total_laps − 1]`, with `life` SOFT 20, MEDIUM 28, HARD 38; a driver who has used two dry compounds SHALL make no simulated stop. A stop SHALL add the pit loss and switch to HARD after SOFT or MEDIUM, or to MEDIUM after HARD.

#### Scenario: Stop window

##### Example: MEDIUM at tyre age 10 on lap 15 of 57

- **GIVEN** a driver on MEDIUM with tyre age 10 at lap 15 who has used only MEDIUM
- **WHEN** the pit plan is sampled
- **THEN** every sampled stop lap is between 30 and 36 and the new compound is HARD

#### Scenario: No stop window left

- **WHEN** a driver who has used only MEDIUM is simulated from lap 56 of 57
- **THEN** no simulated run contains a stop for that driver

#### Scenario: Two compounds used

- **WHEN** a driver has used MEDIUM and HARD by lap 30
- **THEN** no simulated run contains a stop for that driver

### Requirement: Dirty-air penalty

When a simulated driver ends a lap less than 1.0 s behind the car ahead, the system SHALL add 0.4 s to that driver's next simulated lap.

#### Scenario: Slightly faster car stays behind

- **WHEN** a car 0.5 s behind is 0.2 s per lap faster with zero noise
- **THEN** it does not pass within 10 simulated laps

### Requirement: Finishing-position probabilities

For each driver the system SHALL report `p_win`, `p_podium`, `p_points` (shares of runs finishing P1, P1-3, P1-10), `expected_position` (mean), and `position_p10`, `position_p90`, ordered by `expected_position`. Across drivers `p_win` SHALL sum to 1, `p_podium` to 3, and `p_points` to min(10, number of drivers), each within 0.001.

#### Scenario: Probability sums

- **WHEN** predictions are computed for any lap of a 20-driver race
- **THEN** the sums are 1, 3, and 10 within 0.001

### Requirement: Serve position predictions

`python -m augur.analyze` SHALL store predictions for every lap in `position_predictions` for the analyzed model, replacing earlier rows for that race and model. `GET /api/races/{race_id}/positions?lap=N` SHALL return `{race_id, lap, model, analyzed, runs, seed, drivers}` for the `AUGUR_MODEL` model, and `GET /api/races/{race_id}/positions/history?lap=N` SHALL return `{race_id, model, analyzed, laps}` with per-lap `p_win`, `p_podium`, and `expected_position` for laps 1 to N only, in ascending lap order. Both responses SHALL always include `analyzed`; when the race has no predictions for the model, `analyzed` SHALL be `false` with empty `drivers` or `laps`. Field names and nesting SHALL match the API contract in design.md, which the `race-dashboard` mocks follow. Unknown races SHALL return 404 and invalid laps 422.

#### Scenario: History stops at the current lap

- **WHEN** the client calls `positions/history?lap=12`
- **THEN** the response contains exactly laps 1 to 12

#### Scenario: Race not analyzed

- **WHEN** the client calls `positions?lap=5` and `positions/history?lap=5` for a race with no stored predictions for the `AUGUR_MODEL` model
- **THEN** both responses have status 200 and `analyzed` is `false`, `drivers` and `laps` are empty, and `runs` and `seed` are `null`

#### Scenario: Response shape matches the contract

- **WHEN** the client calls both endpoints for an analyzed race
- **THEN** `analyzed` is `true` and the field names and nesting are exactly those in the design.md API contract, with no extra or missing fields
