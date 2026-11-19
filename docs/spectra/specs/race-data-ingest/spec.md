# race-data-ingest Specification

## Purpose

Download historical Formula 1 races from the public OpenF1 API and store their lap-level data and race metadata locally, so every other AUGUR feature works offline from one consistent dataset without an account or subscription.

## Requirements

### Requirement: Ingest races from OpenF1

The system SHALL provide the command `python -m augur.ingest --year <year> --rounds <round> [<round> ...]` that resolves each round to the OpenF1 race session of that year, downloads its laps, stints, pit stops, drivers, and race control messages without authentication, and stores the race under the data directory. Round R SHALL be the R-th non-cancelled `Race` session of the year ordered by start time. The command SHALL print `ingested <race_id>: <n_drivers> drivers, <n_laps> laps` for each stored race and exit with code 0 when every round succeeds. The command SHALL NOT depend on FastF1.

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

#### Scenario: Round numbers skip cancelled races

- **WHEN** a year's OpenF1 race sessions, ordered by start time, are A, B (cancelled), C
- **THEN** round 1 resolves to A and round 2 resolves to C
- **AND** round 3 fails with reason `no race session for round 3`


<!-- @trace
source: race-data-replay
updated: 2026-11-19
code:
  - backend/src/augur/feed.py
  - backend/src/augur/schema.py
  - backend/src/augur/ingest.py
  - backend/pyproject.toml
  - backend/src/augur/replay.py
  - backend/src/augur/storage.py
  - backend/src/augur/state.py
  - backend/src/augur/api.py
  - backend/src/augur/__init__.py
  - backend/src/augur/catalog.py
tests:
  - backend/tests/test_state.py
  - backend/tests/test_feed.py
  - backend/tests/test_normalize.py
  - backend/tests/test_no_future_leak.py
  - backend/tests/conftest.py
  - backend/tests/test_storage.py
  - backend/tests/test_api.py
  - backend/tests/test_replay.py
  - backend/tests/test_package.py
  - backend/tests/test_fixture.py
  - backend/tests/test_ingest_cli.py
-->

---
### Requirement: Normalized lap schema

The stored `laps.parquet` SHALL contain exactly the columns `driver`, `team`, `lap`, `lap_time_s`, `session_time_s`, `stint`, `compound`, `tyre_life`, `pit_in`, `pit_out`, `track_status`, `is_accurate`. Durations SHALL be stored as float seconds. Missing source values SHALL be stored as null, not as zero. `session_time_s` SHALL be the lap end time (`date_start` plus `lap_duration`) minus the race session start, in seconds. `tyre_life` SHALL be `tyre_age_at_start + (lap - lap_start) + 1` of the driver's stint covering the lap. `pit_in` SHALL be true when OpenF1 records a pit stop for the driver on that lap. `is_accurate` SHALL be true only when the lap time is present, the lap number is greater than 1, and the lap is neither a pit-in nor a pit-out lap.

#### Scenario: Convert OpenF1 laps

- **WHEN** the normalizer receives OpenF1 laps, stints, pit, drivers, and race control payloads for a session
- **THEN** it returns a table with the normalized columns and durations in seconds

##### Example: one lap row

- **GIVEN** a session starting at 2024-03-02T15:00:00Z, driver 1 with `name_acronym` "VER" and `team_name` "Red Bull Racing", an OpenF1 lap with `lap_number` 18, `date_start` 2024-03-02T15:30:00Z, `lap_duration` 96.512, `is_pit_out_lap` true, a stint with `stint_number` 2, `lap_start` 18, `lap_end` 37, `compound` "HARD", `tyre_age_at_start` 0, a pit row on lap 17, and no race control message during the lap
- **WHEN** it is normalized
- **THEN** the lap 18 row has `driver` "VER", `team` "Red Bull Racing", `lap` 18, `lap_time_s` 96.512, `session_time_s` 1896.512, `stint` 2, `compound` "HARD", `tyre_life` 1, `pit_in` false, `pit_out` true, `track_status` "1", `is_accurate` false
- **AND** the driver's lap 17 row has `pit_in` true

#### Scenario: Missing lap time

- **WHEN** an OpenF1 lap has `lap_duration` null
- **THEN** the normalized `lap_time_s` and `session_time_s` are null
- **AND** `track_status` is null and `is_accurate` is false

#### Scenario: Missing OpenF1 field

- **WHEN** an OpenF1 laps payload lacks the `lap_duration` field
- **THEN** the normalizer raises a `KeyError` whose message names `lap_duration`


<!-- @trace
source: race-data-replay
updated: 2026-11-19
code:
  - backend/src/augur/feed.py
  - backend/src/augur/schema.py
  - backend/src/augur/ingest.py
  - backend/pyproject.toml
  - backend/src/augur/replay.py
  - backend/src/augur/storage.py
  - backend/src/augur/state.py
  - backend/src/augur/api.py
  - backend/src/augur/__init__.py
  - backend/src/augur/catalog.py
tests:
  - backend/tests/test_state.py
  - backend/tests/test_feed.py
  - backend/tests/test_normalize.py
  - backend/tests/test_no_future_leak.py
  - backend/tests/conftest.py
  - backend/tests/test_storage.py
  - backend/tests/test_api.py
  - backend/tests/test_replay.py
  - backend/tests/test_package.py
  - backend/tests/test_fixture.py
  - backend/tests/test_ingest_cli.py
-->

---
### Requirement: Derived track status

The normalizer SHALL derive `track_status` for each lap from OpenF1 race control messages using FastF1 codes: `"1"` green, `"2"` yellow, `"4"` safety car, `"5"` red flag, `"6"` virtual safety car. The value SHALL be the most severe status active at any time during the lap window `[date_start, date_start + lap_duration]`, with severity `5 > 4 > 6 > 2 > 1`. A track-scope `GREEN` or `CLEAR` flag SHALL end the red flag, safety car, and all sector yellows; a sector `CLEAR` flag SHALL end the yellow in that sector; `VIRTUAL SAFETY CAR ENDING` SHALL end the virtual safety car.

#### Scenario: Status during a lap

- **WHEN** laps are normalized against race control messages
- **THEN** each lap's `track_status` is the most severe status active during its window

##### Example: status per lap window

| Race control messages (time after session start) | Lap window (s) | track_status |
| ------------------------------------------------- | -------------- | ------------ |
| none | 100–196 | `"1"` |
| sector 2 `YELLOW` at 150, sector 2 `CLEAR` at 160 | 100–196 | `"2"` |
| sector 2 `YELLOW` at 150, sector 2 `CLEAR` at 160 | 200–296 | `"1"` |
| `VIRTUAL SAFETY CAR DEPLOYED` at 150, `VIRTUAL SAFETY CAR ENDING` at 400 | 200–296 | `"6"` |
| `SAFETY CAR DEPLOYED` at 150, track `GREEN` at 500 | 200–296 | `"4"` |
| sector 1 `YELLOW` at 120, `SAFETY CAR DEPLOYED` at 150 | 100–196 | `"4"` |
| track `RED` at 150, track `GREEN` at 900 | 100–196 | `"5"` |


<!-- @trace
source: race-data-replay
updated: 2026-11-19
code:
  - backend/src/augur/feed.py
  - backend/src/augur/schema.py
  - backend/src/augur/ingest.py
  - backend/pyproject.toml
  - backend/src/augur/replay.py
  - backend/src/augur/storage.py
  - backend/src/augur/state.py
  - backend/src/augur/api.py
  - backend/src/augur/__init__.py
  - backend/src/augur/catalog.py
tests:
  - backend/tests/test_state.py
  - backend/tests/test_feed.py
  - backend/tests/test_normalize.py
  - backend/tests/test_no_future_leak.py
  - backend/tests/conftest.py
  - backend/tests/test_storage.py
  - backend/tests/test_api.py
  - backend/tests/test_replay.py
  - backend/tests/test_package.py
  - backend/tests/test_fixture.py
  - backend/tests/test_ingest_cli.py
-->

---
### Requirement: Idempotent re-ingest

Running the ingest command again for an already stored race SHALL replace that race's Parquet file and catalog rows. It SHALL NOT create duplicate `races` or `drivers` rows.

#### Scenario: Ingest the same race twice

- **WHEN** the user ingests 2024 round 1 twice
- **THEN** the `races` table has exactly one row for `2024-01-bahrain-grand-prix`
- **AND** the `drivers` table has no duplicate `(race_id, code)` pairs


<!-- @trace
source: race-data-replay
updated: 2026-11-19
code:
  - backend/src/augur/feed.py
  - backend/src/augur/schema.py
  - backend/src/augur/ingest.py
  - backend/pyproject.toml
  - backend/src/augur/replay.py
  - backend/src/augur/storage.py
  - backend/src/augur/state.py
  - backend/src/augur/api.py
  - backend/src/augur/__init__.py
  - backend/src/augur/catalog.py
tests:
  - backend/tests/test_state.py
  - backend/tests/test_feed.py
  - backend/tests/test_normalize.py
  - backend/tests/test_no_future_leak.py
  - backend/tests/conftest.py
  - backend/tests/test_storage.py
  - backend/tests/test_api.py
  - backend/tests/test_replay.py
  - backend/tests/test_package.py
  - backend/tests/test_fixture.py
  - backend/tests/test_ingest_cli.py
-->

---
### Requirement: Ingest failure leaves no partial data

When loading or storing a round fails, the system SHALL write no Parquet file and no catalog rows for that round, SHALL print `failed <year> round <round>: <reason>`, SHALL continue with the remaining rounds, and SHALL exit with code 1.

#### Scenario: One invalid round among valid rounds

- **WHEN** the user runs `python -m augur.ingest --year 2024 --rounds 1 99`
- **THEN** race 2024 round 1 is stored
- **AND** the output contains `failed 2024 round 99:`
- **AND** no data exists for round 99
- **AND** the command exits with code 1

<!-- @trace
source: race-data-replay
updated: 2026-11-19
code:
  - backend/src/augur/feed.py
  - backend/src/augur/schema.py
  - backend/src/augur/ingest.py
  - backend/pyproject.toml
  - backend/src/augur/replay.py
  - backend/src/augur/storage.py
  - backend/src/augur/state.py
  - backend/src/augur/api.py
  - backend/src/augur/__init__.py
  - backend/src/augur/catalog.py
tests:
  - backend/tests/test_state.py
  - backend/tests/test_feed.py
  - backend/tests/test_normalize.py
  - backend/tests/test_no_future_leak.py
  - backend/tests/conftest.py
  - backend/tests/test_storage.py
  - backend/tests/test_api.py
  - backend/tests/test_replay.py
  - backend/tests/test_package.py
  - backend/tests/test_fixture.py
  - backend/tests/test_ingest_cli.py
-->