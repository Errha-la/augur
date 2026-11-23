# position-prediction Specification

## Purpose

Give viewers, at any lap, the probability that each driver wins, reaches the podium, or scores points, by simulating the rest of the race for the whole field from data available up to that lap.

## Requirements

### Requirement: Simulate the remaining race for every driver

For lap N the system SHALL simulate laps N+1 to `total_laps` for all drivers `runs` times (default 1000) with seed `seed + N` (default seed 42), starting from each driver's cumulative time and laps completed at lap N. It SHALL read race data only through `feed.laps_until(N)`. A simulated lap SHALL be the driver's recent pace plus the lap-time model's next-lap delta multiplied by `MODEL_DELTA_DECAY` to the power (lap − N − 1), plus projected degradation, minus fuel gain, plus (after a simulated stop) the new compound's pace offset minus the current compound's, plus a pace offset drawn once per run and driver from Normal(0, `PACE_OFFSET_SD_S`), plus independent lap noise, the expected pit plan, the dirty-air penalty, and neutralised periods. The projected degradation SHALL use a driver's own stint slope only when the fit has at least 8 clean laps and a non-negative slope; otherwise it SHALL use the guarded compound slope: the median of stint fits with at least 8 clean laps, shrunk toward the circuit prior or the per-compound default with weight `DEG_SHRINK_STINTS`. Every projected slope SHALL lie in [0, `DEG_CAP_S_PER_LAP`].

#### Scenario: Dominant leader

- **WHEN** the leader is 30 s ahead of P2 with 3 laps left and both have similar pace
- **THEN** the leader's `p_win` is at least 0.95

#### Scenario: Deterministic per lap

- **WHEN** predictions for lap 20 are computed twice with the same data, model, and seed
- **THEN** both results are identical

#### Scenario: Short or negative stint fit

- **WHEN** a driver's current stint fit has a slope of −0.164 s/lap, or a slope of 0.334 s/lap from 5 clean laps, and the guarded compound slope for that compound is 0.05 s/lap
- **THEN** the projected degradation for that driver is 0.05 s/lap

#### Scenario: Guarded compound slope ignores short stints

##### Example: shrinkage toward the prior

- **GIVEN** HARD stint fits up to lap N of 0.41 s/lap (5 clean laps), 0.06 s/lap (9 clean laps), and 0.04 s/lap (10 clean laps), a HARD circuit prior of 0.03 s/lap, and `DEG_SHRINK_STINTS` 3
- **WHEN** the guarded HARD slope is computed
- **THEN** it is (2 × 0.05 + 3 × 0.03) / 5 = 0.038 s/lap

#### Scenario: Model delta fades

- **WHEN** a driver's recent pace is 90.0 s, the model predicts 88.0 s for the next lap, `MODEL_DELTA_DECAY` is 0.5, and degradation, fuel, offsets, and noise are zero
- **THEN** the driver's simulated laps N+1, N+2, N+3 are 88.0 s, 89.0 s, and 89.5 s

#### Scenario: Uncertainty grows with laps remaining

- **WHEN** two drivers with identical state and pace are simulated from a lap with 40 laps left and from a lap with 5 laps left
- **THEN** the standard deviation of their finishing-time difference over the runs is larger from the lap with 40 laps left

#### Scenario: Altered future laps

- **WHEN** rows with lap greater than 20 are altered and predictions for lap 20 are computed again
- **THEN** the results are identical to the original

---
### Requirement: Expected pit plan

A driver who has not used two different dry compounds by lap N SHALL make exactly one simulated stop when N < total_laps − 1, and no stop when N = total_laps − 1 because the stop window is empty, on lap `N + max(1, life − tyre_age) + U{−3..3}` clipped to `[N+1, total_laps − 1]`, with `life` SOFT 20, MEDIUM 28, HARD 38; a driver who has used two dry compounds SHALL make no simulated stop. A stop SHALL add the pit loss and switch to HARD after SOFT or MEDIUM, or to MEDIUM after HARD. When a neutralised period starts before a driver's sampled stop lap, the driver SHALL move the stop to the period's first lap with probability `SC_PIT_PROB`, paying the reduced pit loss of that period.

#### Scenario: Stop window

##### Example: MEDIUM at tyre age 10 on lap 15 of 57

- **GIVEN** a driver on MEDIUM with tyre age 10 at lap 15 who has used only MEDIUM, and no neutralised period in the run
- **WHEN** the pit plan is sampled
- **THEN** every sampled stop lap is between 30 and 36 and the new compound is HARD

#### Scenario: No stop window left

- **WHEN** a driver who has used only MEDIUM is simulated from lap 56 of 57
- **THEN** no simulated run contains a stop for that driver

#### Scenario: Two compounds used

- **WHEN** a driver has used MEDIUM and HARD by lap 30
- **THEN** no simulated run contains a stop for that driver

#### Scenario: Stop taken under a safety car

- **WHEN** `SC_PROB_PER_LAP` is forced to 1 and `SC_PIT_PROB` to 1 for a run from lap 15 of 57 for a driver on MEDIUM with tyre age 10
- **THEN** the driver stops on lap 16 and pays `SC_PIT_LOSS_FACTOR` times the pit loss

---
### Requirement: Dirty-air penalty

When a simulated driver ends a lap less than 1.0 s behind the car ahead, the system SHALL add 0.4 s to that driver's next simulated lap.

#### Scenario: Slightly faster car stays behind

- **WHEN** a car 0.5 s behind is 0.2 s per lap faster with zero noise
- **THEN** it does not pass within 10 simulated laps

---
### Requirement: Finishing-position probabilities

For each driver the system SHALL report `p_win`, `p_podium`, `p_points` (shares of runs finishing P1, P1-3, P1-10), `expected_position` (mean), and `position_p10`, `position_p90`, ordered by `expected_position`. Across drivers `p_win` SHALL sum to 1, `p_podium` to 3, and `p_points` to min(10, number of drivers), each within 0.001.

#### Scenario: Probability sums

- **WHEN** predictions are computed for any lap of a 20-driver race
- **THEN** the sums are 1, 3, and 10 within 0.001

---
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

---
### Requirement: Neutralised periods

Each simulated run SHALL contain at most one neutralised period. For each lap j from N+1 to `total_laps − 2`, a safety car SHALL start with probability `SC_PROB_PER_LAP` and otherwise a virtual safety car with probability `VSC_PROB_PER_LAP`, until one has started. A safety car SHALL last `SC_LAPS` laps and a virtual safety car `VSC_LAPS` laps, truncated at `total_laps`. During the period every simulated lap SHALL be slowed by the same amount for every car, (`SC_LAP_FACTOR` − 1) or (`VSC_LAP_FACTOR` − 1) times the field's median base pace, the dirty-air penalty SHALL not apply, and the pit loss SHALL be multiplied by `SC_PIT_LOSS_FACTOR` or `VSC_PIT_LOSS_FACTOR`. At the end of a safety car's first lap, every car's gap to the car ahead on the same lap count SHALL be at most `SC_GAP_S`, with the order unchanged. A virtual safety car SHALL add no gap change of its own (cars keep their own pace differences). Cars without a timed lap SHALL keep their time when a safety car closes the gaps.

#### Scenario: Safety car compresses the field

- **WHEN** a safety car is forced to start on lap N+1 and P2 was 12 s behind P1 at lap N, with zero noise and equal pace
- **THEN** at the end of lap N+1 P2 is at most `SC_GAP_S` behind P1 and still second

#### Scenario: No safety cars

- **WHEN** `SC_PROB_PER_LAP` and `VSC_PROB_PER_LAP` are 0
- **THEN** no run contains a neutralised period and lap times are not scaled

---
### Requirement: Finishing-position distribution

For each driver the simulator SHALL report `position_distribution`, a list with one share per finishing position P1 to Pn (n = number of drivers), each list summing to 1 within 0.001, and for each position the shares across drivers SHALL sum to 1 within 0.001. `python -m augur.analyze` SHALL store the list with each per-lap prediction. A database created before this column existed SHALL gain the column when opened, with null for old rows. Storing the distribution SHALL not change the `/positions` and `/positions/history` responses.

#### Scenario: Distribution sums

- **WHEN** predictions are computed for any lap of a 20-driver race
- **THEN** every driver's `position_distribution` has 20 elements summing to 1 within 0.001, and each position's shares across drivers sum to 1 within 0.001

#### Scenario: Old database

- **WHEN** `python -m augur.analyze` runs on a database whose `position_predictions` table has no `position_distribution` column
- **THEN** the column is added, the race's new rows store the distribution, and the `/positions` response has the same fields as before
