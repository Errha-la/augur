## Purpose

Predict each driver's next lap time during a replay from data available up to the current lap, and report the model's measured accuracy against a naive baseline.

## ADDED Requirements

### Requirement: Leakage-safe lap features

The system SHALL build model features for lap k only from rows with lap lower than k. A clean lap SHALL have a lap time, lap greater than 1, no pit in or pit out, track status "1", `is_accurate` true, compound SOFT, MEDIUM, or HARD, and a lap time no more than 10% slower than the fastest clean lap of the race before lap k. `recent_pace_s` SHALL be the median of the driver's last 3 clean laps before lap k. `circuit_deg_prior_s` SHALL be the median stint degradation for the driver's current compound in the most recent earlier season's race at the same `location`, or null when no such race is ingested. `team_pace_gap_s` SHALL be the median of the team's clean laps in the 5 laps before lap k minus the median of all clean laps in that window. Driver identity SHALL NOT be a feature.

#### Scenario: Circuit prior lookup

- **WHEN** features are built for a 2024 race
- **THEN** the prior comes from the 2023 race at the same location, or is null when that race is not ingested

##### Example: priors by season

| Race | Prior race used | circuit_deg_prior_s |
| ---- | --------------- | ------------------- |
| 2024 Bahrain (Sakhir), MEDIUM | 2023 round 1, Sakhir (ingested) | 2023 Sakhir median MEDIUM stint slope |
| 2024 Abu Dhabi (Yas Island), HARD | 2023 round 22, Yas Island (ingested) | 2023 Yas Island median HARD stint slope |
| 2024 Chinese GP (Shanghai), MEDIUM | no 2023 race at Shanghai | null |
| 2024 Abu Dhabi (Yas Island), HARD | 2023 Yas Island not ingested | null |

#### Scenario: Team pace gap

##### Example: two teams

- **GIVEN** in laps 15-19 the team's clean laps have median 94.6 s and all clean laps have median 95.0 s
- **WHEN** features are built for lap 20
- **THEN** `team_pace_gap_s` is -0.4

#### Scenario: Recent pace uses earlier clean laps only

- **WHEN** features are built for a driver's lap 6
- **THEN** `recent_pace_s` is computed from clean laps before lap 6 and ignores pit laps and non-green laps

##### Example: pit lap skipped

- **GIVEN** clean lap times: lap 2 = 95.0, lap 3 = 95.4, lap 4 is a pit-in lap (118.0), lap 5 = 95.2
- **WHEN** features are built for lap 6
- **THEN** `recent_pace_s` is 95.2 (median of 95.0, 95.4, 95.2)

### Requirement: Train and evaluate the lap-time model

`python -m augur.train --model <name>` (default `lightgbm`) SHALL train the named model on the delta between the next clean lap time and `recent_pace_s`, using the `--train` races (default 2024 rounds 2-11), and SHALL evaluate on the `--test` races (default 2024 rounds 1 and 24). `--train` and `--test` SHALL take the form `<year>:<rounds>`, where rounds is a comma-separated list of rounds or ranges such as `2-11` or `1,24`. It SHALL write `data/models/<name>.joblib` and `data/models/<name>_metrics.json` containing `model`, `author`, `train_races`, `test_races`, `n_train`, `n_test`, `mae_model_s`, `mae_baseline_s`, `trained_at`, where the baseline predicts a delta of 0. Train and test races SHALL NOT overlap.

#### Scenario: Metrics file written

- **WHEN** training completes
- **THEN** the metrics file contains both MAE values in seconds and the command prints them

#### Scenario: Default test races

- **WHEN** the user runs `python -m augur.train` without options
- **THEN** `data/models/lightgbm_metrics.json` lists `test_races` `2024-01-bahrain-grand-prix` and `2024-24-abu-dhabi-grand-prix`
- **AND** `train_races` lists the ten 2024 races of rounds 2 to 11, from `2024-02-saudi-arabian-grand-prix` to `2024-11-austrian-grand-prix`

#### Scenario: Overlapping train and test races

- **WHEN** the user runs `python -m augur.train --train 2024:1-11 --test 2024:1,24`
- **THEN** the command prints `train and test races overlap: 2024-01-bahrain-grand-prix` and exits with code 1

#### Scenario: Training race not ingested

- **WHEN** a listed race has not been ingested
- **THEN** the command prints `missing race <label>, run augur.ingest first` and exits with code 1, where the label is `<year>-<rr>` because the race's event name is unknown before ingest

##### Example: missing round

- **GIVEN** 2024 round 5 is not ingested
- **WHEN** the user runs `python -m augur.train --train 2024:2-11`
- **THEN** the output is `missing race 2024-05, run augur.ingest first`

### Requirement: Pluggable lap-time models

The system SHALL define a `LapTimeModel` protocol with attributes `name` and `author` and methods `fit`, `predict`, `save`, and `load`, and SHALL keep a registry that maps a model name to its class. The built-in models SHALL be `lightgbm` and `baseline`. Commands SHALL select a model with `--model <name>`, the API SHALL serve the model named by the `AUGUR_MODEL` environment variable (default `lightgbm`), and an unregistered name SHALL make a command print `unknown model <name>` and exit with code 1.

#### Scenario: Custom model registered

- **WHEN** a developer registers a class named `mymodel` that implements the protocol and runs `python -m augur.train --model mymodel`
- **THEN** `data/models/mymodel.joblib` and `data/models/mymodel_metrics.json` exist and the metrics file has `model` `mymodel` and the class's `author`

#### Scenario: Unknown model

- **WHEN** the user runs `python -m augur.train --model nope`
- **THEN** the command prints `unknown model nope` and exits with code 1

### Requirement: Serve next-lap predictions

`GET /api/races/{race_id}/predictions?lap=N` SHALL return, per driver, `predicted_next_lap_s`, `recent_pace_s`, `deg_s_per_lap`, `deg_laps`, and `cliff`, computed only from laps up to N. Fields SHALL be null when the driver has fewer than 3 clean laps. The response at lap N SHALL be identical when rows with lap greater than N are altered.

#### Scenario: Not enough clean laps

- **WHEN** the client requests predictions at lap 2
- **THEN** every driver has `predicted_next_lap_s` null

#### Scenario: Altered future laps

- **WHEN** rows with lap greater than N are altered
- **THEN** the predictions response at lap N is unchanged
