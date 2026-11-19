## Purpose

Serve ingested races to the dashboard and analysis code lap by lap, so a race can be replayed as if it were live. Every response is computed only from laps up to the requested lap.

## ADDED Requirements

### Requirement: List ingested races

`GET /api/races` SHALL return every race in the catalog as `{race_id, year, round, event_name, date, total_laps}`, ordered by year then round. It SHALL return an empty list when no race is ingested.

#### Scenario: Two races ingested

- **WHEN** races 2024 round 1 and 2023 round 11 are ingested and the client calls `GET /api/races`
- **THEN** the response lists `2023-11-hungarian-grand-prix` before `2024-01-bahrain-grand-prix`

### Requirement: Race state at a lap

`GET /api/races/{race_id}/state?lap=N` SHALL return `{race_id, lap, total_laps, track_status, drivers}`, where `track_status` is the leader's track status on its last completed lap. Each driver entry SHALL contain `code`, `team`, `team_color`, `position`, `laps_completed`, `last_lap_time_s`, `compound`, `tyre_age_laps`, `stint`, `pit_count`, `gap_to_leader_s`, `laps_behind_leader`, taken from that driver's last completed lap L with L <= N. Position SHALL be the rank by laps completed (descending) then session time at lap L (ascending). `gap_to_leader_s` SHALL be the driver's session time at lap L minus the leader's session time at lap L. `pit_count` SHALL equal `stint - 1`. `laps_behind_leader` SHALL equal the leader's `laps_completed` minus L.

#### Scenario: State at lap 3 of a fixture race

- **WHEN** the client requests the state at lap 3
- **THEN** drivers are ordered by computed position and each entry reflects its last completed lap up to lap 3

##### Example: three drivers

- **GIVEN** at lap 3: A completed 3 laps at session time 300.0 s; B completed 3 laps at 302.5 s on stint 2; C completed 2 laps at 210.0 s
- **WHEN** the client requests `state?lap=3`
- **THEN** positions are A=1, B=2, C=3
- **AND** B has `gap_to_leader_s` 2.5 and `pit_count` 1
- **AND** C has `laps_completed` 2 and `laps_behind_leader` 1

### Requirement: Lap history up to a lap

`GET /api/races/{race_id}/laps?lap=N` SHALL return the normalized lap rows with `lap <= N`, ordered by driver then lap. With the optional `driver=CODE` parameter it SHALL return only that driver's rows.

#### Scenario: Filter by driver

- **WHEN** the client calls `laps?lap=4&driver=VER`
- **THEN** the response contains only rows with `driver` "VER" and `lap` 1 to 4

### Requirement: Race feed interface

The system SHALL define a `RaceFeed` protocol with `race_id`, `total_laps`, `latest_lap()`, and `laps_until(lap)`, and SHALL provide `ReplayFeed`, which reads through `ReplayStore.laps_until` and returns `total_laps` from `latest_lap()`. The API handlers SHALL obtain race data only through a `RaceFeed`.

#### Scenario: Replay feed

- **WHEN** a `ReplayFeed` is created for the 5-lap fixture race
- **THEN** `latest_lap()` returns 5 and `laps_until(3)` returns only rows with lap 1 to 3

### Requirement: No future data in replay responses

All replay responses SHALL be computed through a single read method `ReplayStore.laps_until(race_id, lap)` that returns only rows with `lap <= lap`. The response for lap N SHALL be identical regardless of the content of rows with lap greater than N. No response SHALL include the final race classification.

#### Scenario: Altered future laps

- **WHEN** every fixture row with lap greater than 3 is changed (lap times, compounds, stints) and the client requests `state?lap=3` and `laps?lap=3`
- **THEN** both responses are byte-for-byte equal to the responses before the change

### Requirement: Invalid replay requests

The API SHALL return 404 with `{"detail": "race not found"}` for an unknown `race_id`, 404 with `{"detail": "driver not found"}` for an unknown `driver`, and 422 when `lap` is missing, below 1, or above the race's `total_laps`.

#### Scenario: Request validation

##### Example: error cases

| Request | Status | Body detail |
| ------- | ------ | ----------- |
| `/api/races/nope/state?lap=1` | 404 | race not found |
| `/api/races/<id>/state?lap=0` | 422 | validation error |
| `/api/races/<id>/state?lap=<total_laps+1>` | 422 | validation error |
| `/api/races/<id>/state` | 422 | validation error |
| `/api/races/<id>/laps?lap=2&driver=XXX` | 404 | driver not found |
