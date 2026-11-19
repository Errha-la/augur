# strategy-simulation Specification

## Purpose

Compare pit-stop options for one driver at a replay lap with a seeded Monte Carlo simulation, so AUGUR can say which strategy is likely fastest and how certain that is.

## Requirements

### Requirement: Candidate pit strategies

For driver D at lap N, the system SHALL simulate "pit on lap N+k" for each k in {1, 3, 5, 8} where N+k is lower than `total_laps - 1`, and SHALL add "no further stop" only when D has already used two different dry compounds up to lap N. Each simulated lap time SHALL be base pace plus degradation times tyre age plus normal noise; a pit stop SHALL add the pit loss, reset tyre age, and fit HARD tyres, or MEDIUM when the driver's current compound is HARD. Pit loss SHALL be the median observed pit cost up to lap N, or 22.0 s when no stop has been observed.

#### Scenario: Driver who has not used two compounds

- **WHEN** driver D has used only MEDIUM up to lap 15 of 57
- **THEN** the strategies are pit on laps 16, 18, 20, 23 and "no further stop" is absent

#### Scenario: Late in the race

- **WHEN** the lap is 53 of 57
- **THEN** only "pit on lap 54" is offered among the pit options

---
### Requirement: Reproducible Monte Carlo results

For each strategy the system SHALL report `mean_s`, `p10_s`, `p90_s` of the simulated remaining race time and `win_probability` (share of runs in which it is fastest). Strategies SHALL be ordered by `mean_s`. The win probabilities SHALL sum to 1 within 0.001. The same `runs`, `seed`, race, driver, and lap SHALL produce identical output.

#### Scenario: Same seed twice

- **WHEN** the client calls the strategy endpoint twice with `seed=42`
- **THEN** both responses are identical

---
### Requirement: Strategy endpoint validation

`GET /api/races/{race_id}/strategy?lap=N&driver=CODE` SHALL accept optional `runs` (default 1000, allowed 100-5000) and `seed` (default 42), SHALL return `{race_id, lap, driver, runs, seed, pit_loss_s, strategies}`, and SHALL return 422 for `runs` outside the allowed range and 404 for an unknown race or driver.

#### Scenario: Runs out of range

- **WHEN** the client sends `runs=50`
- **THEN** the response status is 422
