## Purpose

Provide the end-of-race Wrapped data in one response, available only once the replay has reached the final lap so it cannot spoil the race.

## ADDED Requirements

### Requirement: Wrapped unlocks at the final lap

`GET /api/races/{race_id}/wrapped?lap=N&driver=CODE` SHALL return 409 with `{"detail": "wrapped unlocks at the final lap"}` when N is lower than `total_laps`, 409 with `{"detail": "race not analyzed"}` when the race has no events or position predictions for the `AUGUR_MODEL` model, and 404 for an unknown race or driver.

#### Scenario: Locked and unlocked

- **WHEN** the Wrapped is requested at different laps of an analyzed 58-lap race
- **THEN** the status follows the cases below

##### Example: 58-lap race

| Request | Status |
| ------- | ------ |
| `wrapped?lap=57&driver=VER` | 409 wrapped unlocks at the final lap |
| `wrapped?lap=58&driver=VER` | 200 |
| `wrapped?lap=58&driver=XXX` | 404 driver not found |

### Requirement: Wrapped content

The 200 response SHALL contain `race_id`, `event_name`, `year`, `model` (`name`, `author`), `summary` (`winner`, `podium`, `total_laps`, `n_events`, `n_events_by_type`), `podium_call` (`lap`, `predicted`, `actual`, `correct`), `score` (`position_skill_pct`, `brier_model`, `brier_baseline`, `lap_improvement_pct`, `mae_model_s`, `mae_baseline_s`) computed with the same scoring as the bench for this race, `hit_rate`, `best_call`, `biggest_miss`, `biggest_moment`, and `driver` (`code`, `team`, `team_color`, `grid_position`, `final_position`, `positions_by_lap`, `p_podium_by_lap`, `stints`, `events`). `podium_call.lap` SHALL be `floor(0.5 × total_laps)`, `predicted` the three drivers with the highest `p_podium` at that lap, `actual` the final podium, and `correct` the number of predicted drivers on it. `best_call` SHALL be the hit with the highest severity, `biggest_miss` the miss with the highest severity, and `biggest_moment` the event with the highest severity, each breaking ties by the earliest lap and each null when none exists.

#### Scenario: Picking the highlights

##### Example: four events

- **GIVEN** events: lap 10 `degradation_warning` severity 70 hit; lap 18 `undercut_window` severity 60 hit; lap 30 `undercut_window` severity 60 miss; lap 44 `position_change` severity 90 no outcome
- **WHEN** the Wrapped is requested at the final lap
- **THEN** `best_call` is the lap 10 event, `biggest_miss` is the lap 30 event, and `biggest_moment` is the lap 44 event

#### Scenario: Podium call

##### Example: two of three

- **GIVEN** a 58-lap race where at lap 29 the highest `p_podium` values are VER 0.92, NOR 0.71, LEC 0.55, and the final podium is VER, LEC, PIA
- **WHEN** the Wrapped is requested at lap 58
- **THEN** `podium_call` is lap 29, predicted VER, NOR, LEC, actual VER, LEC, PIA, `correct` 2

#### Scenario: Score matches the bench

- **WHEN** the Wrapped for `2024-01-bahrain-grand-prix` is requested and `bench/lightgbm.json` exists from the same data
- **THEN** `score.position_skill_pct` and `score.lap_improvement_pct` equal that race's values in `per_race`
