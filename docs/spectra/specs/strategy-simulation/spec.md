# strategy-simulation Specification

## Purpose

Compare pit-stop options for one driver at a replay lap with a seeded Monte Carlo simulation, so AUGUR can say which strategy is likely fastest and how certain that is.

## Requirements

### Requirement: Candidate pit strategies

For driver D at lap N, the system SHALL simulate "pit on lap N+k" for each k in {1, 3, 5, 8} where N+k is lower than `total_laps - 1`, and SHALL add "no further stop" only when D has already used two different dry compounds up to lap N. Each simulated lap time SHALL be base pace plus the compound pace offset plus degradation times tyre age minus fuel gain plus normal noise; a pit stop SHALL add the pit loss, reset tyre age, and fit HARD tyres, or MEDIUM when the driver's current compound is HARD, using the guarded compound slope and the compound pace offset of the new compound. Pit loss SHALL be the median observed pit cost up to lap N, or 22.0 s when no stop has been observed.

#### Scenario: Driver who has not used two compounds

- **WHEN** driver D has used only MEDIUM up to lap 15 of 57
- **THEN** the strategies are pit on laps 16, 18, 20, 23 and "no further stop" is absent

#### Scenario: Late in the race

- **WHEN** the lap is 53 of 57
- **THEN** only "pit on lap 54" is offered among the pit options

#### Scenario: Harder compound costs time

- **WHEN** two otherwise identical drivers on MEDIUM are simulated with the same pit lap, one fitting HARD (offset +0.4 s/lap) and one fitting MEDIUM, with zero degradation and noise
- **THEN** the HARD plan's `mean_s` is larger by 0.4 s times the laps after the stop

---
### Requirement: Reproducible Monte Carlo results

For each strategy the system SHALL report `mean_s`, `p10_s`, `p90_s` of the simulated remaining race time and `win_probability` (share of runs in which it is fastest). All candidates of one call SHALL use the same random draws per run: the summed lap noise, the pit loss (standard deviation `STRATEGY_PIT_LOSS_SD_S`), and the degradation slopes of the current and the next compound (standard deviation `STRATEGY_DEG_SD_S_PER_LAP` each, clipped at 0). Strategies SHALL be ordered by `mean_s`. The win probabilities SHALL sum to 1 within 0.001. The same `runs`, `seed`, race, driver, and lap SHALL produce identical output.

#### Scenario: Same seed twice

- **WHEN** the client calls the strategy endpoint twice with `seed=42`
- **THEN** both responses are identical

#### Scenario: Shared draws decide by plan

- **WHEN** two candidates differ only in pit lap and one has a lower expected time in every run because its tyres are fresher for longer
- **THEN** that candidate's `win_probability` is 1.0

---
### Requirement: Strategy endpoint validation

`GET /api/races/{race_id}/strategy?lap=N&driver=CODE` SHALL accept optional `runs` (default 1000, allowed 100-5000) and `seed` (default 42), SHALL return `{race_id, lap, driver, runs, seed, pit_loss_s, strategies}`, and SHALL return 422 for `runs` outside the allowed range and 404 for an unknown race or driver.

#### Scenario: Runs out of range

- **WHEN** the client sends `runs=50`
- **THEN** the response status is 422

---
### Requirement: Pit-lap plan simulation

`strategy.simulate_pit_laps(laps, total_laps, driver, lap, pit_laps, runs, seed)` SHALL simulate each listed pit lap (or `None` for no further stop) with the same model and shared draws as the candidate comparison and return `pit_loss_s` and `plans`, one `{pit_lap, mean_s, p10_s, p90_s}` per input in input order. A pit lap outside [lap+1, total_laps − 2] SHALL raise `ValueError`. For the same pit lap, runs, seed, race, driver, and lap, `mean_s`, `p10_s`, and `p90_s` SHALL equal those of the matching "pit on lap" candidate from the strategy comparison.

#### Scenario: Same numbers as the comparison

- **WHEN** `simulate_pit_laps` is called for lap 15 with pit laps [18] and the strategy comparison is computed for lap 15 with the same runs and seed
- **THEN** the plan for lap 18 has the same `mean_s`, `p10_s`, and `p90_s` as "pit on lap 18"

#### Scenario: Pit lap out of range

- **WHEN** `simulate_pit_laps` is called for lap 15 of 57 with pit laps [15]
- **THEN** it raises `ValueError`
