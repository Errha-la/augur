## Purpose

Give anyone who clones AUGUR one command that scores their model on the same races with the same rules, so results are comparable and reproducible, with finishing-position prediction as the headline.

## ADDED Requirements

### Requirement: Podium skill score

For a race with `total_laps` T, the system SHALL use checkpoints `floor(0.25 × T)`, `floor(0.5 × T)`, and `floor(0.75 × T)`. For every checkpoint c and driver d it SHALL compare the model forecast `p_podium(c, d)` and the baseline forecast (1 when d is P1-P3 at c, else 0) with the outcome (1 when d finishes P1-P3). `brier_model` and `brier_baseline` SHALL be the mean squared errors over all (c, d) pairs, and `position_skill_pct` SHALL be `100 × (1 − brier_model / brier_baseline)` rounded to 1 decimal, or null when `brier_baseline` is 0.

#### Scenario: Checkpoint laps

| total_laps | checkpoints |
| ---------- | ----------- |
| 57 | 14, 28, 42 |
| 58 | 14, 29, 43 |

- **WHEN** the score is computed for a race
- **THEN** the checkpoints follow the table above

#### Scenario: Skill arithmetic

##### Example: one checkpoint, four drivers

- **GIVEN** at the checkpoint the order is A, B, C, D with `p_podium` A 0.9, B 0.8, C 0.5, D 0.4, and the final podium is A, B, D
- **WHEN** the podium skill is computed
- **THEN** `brier_model` is 0.165, `brier_baseline` is 0.5, and `position_skill_pct` is 67.0

#### Scenario: Podium never changed

- **WHEN** the P1-P3 set at every checkpoint equals the final podium
- **THEN** `position_skill_pct` is null

### Requirement: Score a model on the benchmark races

`python -m augur.bench --model <name>` SHALL score the model on `2024-01-bahrain-grand-prix` and `2024-24-abu-dhabi-grand-prix`, analyzing a race first when it has no events or position predictions for that model, and SHALL write `bench/<name>.json` with `model`, `author`, `races`, `position_skill_pct`, `brier_model`, `brier_baseline`, `lap_improvement_pct`, `mae_model_s`, `mae_baseline_s`, `hit_rate`, `per_race`, `seed`, `data_source` ("openf1"), `augur_version`, and `generated_at`. Pooled values SHALL pool checkpoint pairs, clean laps, and events across both races. `lap_improvement_pct` SHALL equal `100 × (mae_baseline_s − mae_model_s) / mae_baseline_s` rounded to 1 decimal. The hit rate SHALL count hits over hits plus misses, excluding voids. The command SHALL print `<name>: podium skill <s>% vs current order, lap times <beat|trail> baseline by <x>%, event hit rate <y>% (<hits>/<resolved>)`, with `podium skill n/a` when the skill is null.

#### Scenario: Summary line

##### Example: pooled scores

- **GIVEN** pooled `brier_model` 0.060 and `brier_baseline` 0.100, `mae_model_s` 0.820 and `mae_baseline_s` 1.000, and 9 hits, 5 misses, 2 voids
- **WHEN** the bench runs for `lightgbm`
- **THEN** the output is `lightgbm: podium skill 40.0% vs current order, lap times beat baseline by 18.0%, event hit rate 64% (9/14)`

#### Scenario: Same model twice

- **WHEN** the bench runs twice for the same model and data
- **THEN** both files are equal except `generated_at`

### Requirement: Benchmark races excluded from training

The bench SHALL exit with code 1 and print `benchmark race <race_id> is in the training set` when the model's metrics file lists a benchmark race in `train_races`, SHALL print `unknown model <name>` for an unregistered model, and SHALL print `missing race <race_id>, run augur.ingest first` when a benchmark race is not ingested. It SHALL write no file in these cases.

#### Scenario: Trained on a benchmark race

- **WHEN** `mymodel_metrics.json` lists `2024-24-abu-dhabi-grand-prix` in `train_races`
- **THEN** the bench prints `benchmark race 2024-24-abu-dhabi-grand-prix is in the training set`, exits with code 1, and `bench/mymodel.json` does not exist
