## Purpose

Serve the data behind AUGUR's strategy charts (race trace, pit-stop clock, pit-window curve, tyre stints, degradation by compound, and finishing-position distribution) at any replay lap, from laps up to that lap only.

## ADDED Requirements

### Requirement: Race trace data

`GET /api/races/{race_id}/trace?lap=N` SHALL return `{race_id, lap, reference_lap_s, drivers}` with drivers in running order at lap N, each `{code, team_color, points}` and points `{lap, delta_s}` ascending by lap for laps 1 to the driver's last completed lap at or before N. Race time SHALL be session time minus the race start, where the race start is the median over drivers of lap-1 session time minus lap-1 lap time. `reference_lap_s` SHALL be the median over drivers with a completed lap of race time at their last completed lap divided by that lap number, and `delta_s` SHALL be `reference_lap_s × lap − race time`.

#### Scenario: Faster driver gains

##### Example: two drivers, three laps

- **GIVEN** a race start at session time 1000.0 s, driver A with race times 90, 180, 270 s and driver B with race times 91, 182, 273 s at laps 1 to 3
- **WHEN** the client calls `trace?lap=3`
- **THEN** `reference_lap_s` is 90.5, A's points are 0.5, 1.0, 1.5 and B's points are −0.5, −1.0, −1.5

#### Scenario: No future laps

- **WHEN** rows with lap greater than 20 are altered and `trace?lap=20` is requested again
- **THEN** the response is identical

### Requirement: Pit rejoin data

`GET /api/races/{race_id}/rejoin?lap=N&driver=D` SHALL return `{race_id, lap, driver, pit_loss_s, lap_length_s, cars, rejoin}`. `cars` SHALL list every car with a gap at lap N in running order as `{code, position, gap_to_leader_s, laps_behind_leader}`. `pit_loss_s` SHALL be the median observed pit cost up to lap N, or 22.0 s when no stop has been observed. `lap_length_s` SHALL be the leader's last lap time when it is a clean lap, else the median of the leader's clean laps up to N, else the median of all lap times up to N. `rejoin` SHALL be `{position, gap_to_leader_s, ahead, ahead_gap_s, behind, behind_gap_s}` for D's projected gap `gap_to_leader_s(D) + pit_loss_s`, with position 1 plus the number of other cars whose gap is at or below the projected gap, or null when D has no gap at N. An unknown driver SHALL return 404.

#### Scenario: Rejoin between two cars

##### Example: four cars

- **GIVEN** at lap N gaps to the leader A 0.0, B 5.0, C 20.0, D 24.0 s, pit loss 21.5 s, and driver B
- **WHEN** the client calls `rejoin?lap=N&driver=B`
- **THEN** `rejoin.position` is 4, `rejoin.gap_to_leader_s` is 26.5, `ahead` is D with `ahead_gap_s` 2.5, and `behind` is null

#### Scenario: Unknown driver

- **WHEN** the client calls `rejoin?lap=10&driver=XXX`
- **THEN** the response status is 404

### Requirement: Pit window data

`GET /api/races/{race_id}/pit-window?lap=N&driver=D` SHALL accept optional `runs` (default 1000, allowed 100-5000) and `seed` (default 42) and SHALL return `{race_id, lap, driver, runs, seed, pit_loss_s, best_pit_lap, plans}`. `plans` SHALL hold one `{pit_lap, mean_s, p10_s, p90_s, delta_s}` for every pit lap from N+1 to `total_laps − 2` in ascending order, plus a plan with `pit_lap` null last when D has used two dry compounds, computed with the strategy simulator's pit-lap plan simulation. `delta_s` SHALL be the plan's `mean_s` minus the lowest `mean_s`. `best_pit_lap` SHALL be the pit lap with the lowest `mean_s`, or null when that plan is the no-stop plan or there are no plans. The same inputs and seed SHALL produce identical output.

#### Scenario: Agrees with the strategy table

- **WHEN** the client calls `pit-window?lap=15&driver=VER` and `strategy?lap=15&driver=VER` with the same runs and seed
- **THEN** the pit-window plan for lap 18 has the same `mean_s`, `p10_s`, and `p90_s` as the strategy "pit on lap 18"

#### Scenario: No window left

- **WHEN** the client calls `pit-window` at lap `total_laps − 1` for a driver who has used one dry compound
- **THEN** `plans` is empty and `best_pit_lap` is null

#### Scenario: Runs out of range

- **WHEN** the client sends `runs=50`
- **THEN** the response status is 422

### Requirement: Stint data

`GET /api/races/{race_id}/stints?lap=N` SHALL return `{race_id, lap, drivers}` in running order at lap N, each `{code, stints}` with stints `{stint, compound, start_lap, end_lap, start_tyre_age}` ascending by stint, where `end_lap` is the stint's last lap at or before N.

#### Scenario: Stint still running

- **WHEN** a driver started stint 2 on lap 26 and the client calls `stints?lap=30`
- **THEN** that driver's stint 2 has `start_lap` 26 and `end_lap` 30

### Requirement: Degradation points data

`GET /api/races/{race_id}/degradation?lap=N` SHALL return `{race_id, lap, compounds}` with one entry per dry compound that has at least one clean lap up to N, in SOFT, MEDIUM, HARD order, each `{compound, fit, points}`. `points` SHALL be the clean laps up to N as `{code, lap, tyre_age, fuel_corrected_s}`. `fit` SHALL be the least-squares line `{slope_s_per_lap, intercept_s, n}` of `fuel_corrected_s` against `tyre_age` over those points, or null when there are fewer than 4 points.

#### Scenario: Too few points

- **WHEN** only 3 clean HARD laps exist up to lap N
- **THEN** the HARD entry lists 3 points and `fit` is null

### Requirement: Position distribution data

`GET /api/races/{race_id}/positions/distribution?lap=N` SHALL return `{race_id, lap, model, analyzed, drivers}` for the `AUGUR_MODEL` model with drivers in the same order as `positions?lap=N`, each `{code, position_distribution}`. When the race has no stored predictions for the model, `analyzed` SHALL be false and `drivers` empty. A row stored before the distribution existed SHALL have `position_distribution` null.

#### Scenario: Not analyzed

- **WHEN** the client calls `positions/distribution?lap=5` for a race with no stored predictions for the `AUGUR_MODEL` model
- **THEN** the status is 200, `analyzed` is false, and `drivers` is empty

#### Scenario: Same order as positions

- **WHEN** the client calls `positions?lap=20` and `positions/distribution?lap=20` for an analyzed race
- **THEN** the driver codes appear in the same order in both responses
