## Purpose

Download historical Formula 1 races from FastF1 and store their lap-level data and race metadata locally, so every other AUGUR feature works offline from one consistent dataset.

## ADDED Requirements

### Requirement: Ingest races from FastF1

The system SHALL provide the command `python -m augur.ingest --year <year> --rounds <round> [<round> ...]` that loads each race session through FastF1 without telemetry and stores it under the data directory. The command SHALL print `ingested <race_id>: <n_drivers> drivers, <n_laps> laps` for each stored race and exit with code 0 when every round succeeds.

#### Scenario: Ingest one race

- **WHEN** the user runs `python -m augur.ingest --year 2024 --rounds 1`
- **THEN** the file `data/races/2024-01-bahrain-grand-prix/laps.parquet` exists
- **AND** `data/augur.sqlite` contains a `races` row with `race_id` `2024-01-bahrain-grand-prix` and one `drivers` row per driver in that race, each with a `team_color` in `#RRGGBB` form, and the `races` row has `location` `Sakhir`
- **AND** the command exits with code 0

##### Example: race_id format

| year | round | event name | race_id |
| ---- | ----- | ---------- | ------- |
| 2024 | 1 | Bahrain Grand Prix | `2024-01-bahrain-grand-prix` |
| 2023 | 11 | Hungarian Grand Prix | `2023-11-hungarian-grand-prix` |
| 2024 | 24 | Abu Dhabi Grand Prix | `2024-24-abu-dhabi-grand-prix` |

### Requirement: Normalized lap schema

The stored `laps.parquet` SHALL contain exactly the columns `driver`, `team`, `lap`, `lap_time_s`, `session_time_s`, `stint`, `compound`, `tyre_life`, `pit_in`, `pit_out`, `track_status`, `is_accurate`. Durations SHALL be stored as float seconds. Missing FastF1 values SHALL be stored as null, not as zero.

#### Scenario: Convert FastF1 laps

- **WHEN** the normalizer receives a FastF1-style laps table
- **THEN** it returns a table with the normalized columns and durations in seconds

##### Example: one lap row

- **GIVEN** a FastF1 row with `Driver` "VER", `LapNumber` 3, `LapTime` 0:01:36.512, `PitInTime` NaT, `PitOutTime` 0:52:10
- **WHEN** it is normalized
- **THEN** the row has `driver` "VER", `lap` 3, `lap_time_s` 96.512, `pit_in` false, `pit_out` true

#### Scenario: Missing lap time

- **WHEN** a FastF1 row has `LapTime` NaT
- **THEN** the normalized `lap_time_s` is null

### Requirement: Idempotent re-ingest

Running the ingest command again for an already stored race SHALL replace that race's Parquet file and catalog rows. It SHALL NOT create duplicate `races` or `drivers` rows.

#### Scenario: Ingest the same race twice

- **WHEN** the user ingests 2024 round 1 twice
- **THEN** the `races` table has exactly one row for `2024-01-bahrain-grand-prix`
- **AND** the `drivers` table has no duplicate `(race_id, code)` pairs

### Requirement: Ingest failure leaves no partial data

When loading or storing a round fails, the system SHALL write no Parquet file and no catalog rows for that round, SHALL print `failed <year> round <round>: <reason>`, SHALL continue with the remaining rounds, and SHALL exit with code 1.

#### Scenario: One invalid round among valid rounds

- **WHEN** the user runs `python -m augur.ingest --year 2024 --rounds 1 99`
- **THEN** race 2024 round 1 is stored
- **AND** the output contains `failed 2024 round 99:`
- **AND** no data exists for round 99
- **AND** the command exits with code 1
