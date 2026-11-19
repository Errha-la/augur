## Context

The repository is empty apart from Spectra and agent instructions. AUGUR is a 2-day portfolio build: FastAPI backend in `backend/`, React dashboard in `frontend/` (later change). This change creates the data foundation that the `prediction-and-events` and `race-dashboard` changes build on. FastF1 is the only data source. The project rule is that nothing computed at replay lap N may read laps after N.

## Goals / Non-Goals

**Goals:**

- One command ingests one or more historical races into `data/` and can be re-run safely.
- One read path for lap data that always takes a lap cutoff.
- HTTP endpoints for the race list, race state at lap N, and lap history up to lap N.
- Tests run offline in seconds.

**Non-Goals:**

- Car telemetry (speed, throttle, GPS traces). Lap-level data is enough for the MVP models and charts.
- OpenF1 or live timing.
- Final race classification in any API response, because it is future information during replay.
- Retirement detection. A driver who stops completing laps shows a growing `laps_behind_leader`.
- Authentication, deployment, database servers.

**Demo races:** 2024 round 1 `2024-01-bahrain-grand-prix` and 2024 round 24 `2024-24-abu-dhabi-grand-prix` (season finale). Both are also the fixed benchmark races used by later changes.

## Decisions

### Lap-level data only, no car telemetry

Load FastF1 sessions with `laps=True, telemetry=False, weather=False, messages=False`. Alternative considered: loading telemetry for richer charts. Rejected because it multiplies download size and ingest time and no MVP model uses it.

### Parquet per race plus SQLite catalog

Each race is stored as `data/races/<race_id>/laps.parquet`. A SQLite file `data/augur.sqlite` holds the `races` and `drivers` tables. Alternative: everything in SQLite. Rejected because Parquet loads straight into pandas for the model work in the next change, and SQLite stays a small catalog. `race_id` format is `<year>-<round two digits>-<slug of event name>`, for example `2024-01-bahrain-grand-prix`.

### Single cutoff read path

`augur.replay.ReplayStore` is the only module that reads `laps.parquet` for serving. Its public read method is `laps_until(race_id, lap)`, which filters `lap <= cutoff` before returning a copy. API handlers and later model code call it and never read Parquet directly. Alternative: filter in each endpoint. Rejected because one missed filter leaks future data silently.

### Race feed interface for replay now and live later

AUGUR will later run on live timing for viewers, so every consumer (API, models, event engine) reads race data through a `RaceFeed` protocol: `race_id`, `total_laps`, `latest_lap() -> int`, and `laps_until(lap) -> DataFrame`. `ReplayFeed(race_id, store)` implements it over `ReplayStore`, with `latest_lap()` returning `total_laps`. A future `LiveFeed` implements the same protocol from OpenF1; it is out of scope here. Alternative: call `ReplayStore` directly everywhere. Rejected because switching to live would touch every consumer.

### Computed positions from laps completed and session time

Race state position is computed as the rank by (laps completed descending, session time at end of last completed lap ascending), not taken from the FastF1 `Position` column, which has gaps. Gap to leader is the driver's session time at their last completed lap L minus the leader's session time at lap L.

### Offline tests with synthetic fixtures

Tests build a small synthetic laps table (3 drivers, 5 laps) in the normalized schema and a fake FastF1-style DataFrame for the normalizer. A single real-download smoke test is marked `network` and skipped by default.

## Implementation Contract

**Ingest command**

- Invocation: `python -m augur.ingest --year 2024 --rounds 1 [2 3 ...]` (run from `backend/` with the package installed). Default data root is `data/` at the repository root; override with `--data-dir`.
- For each round it loads the race session (`"R"`) through FastF1 with the cache directory `data/fastf1-cache/`, normalizes laps, writes `laps.parquet`, and upserts one `races` row and one `drivers` row per driver.
- Prints one line per race: `ingested <race_id>: <n_drivers> drivers, <n_laps> laps`. Exit code 0 when all rounds succeed.
- On any failure for a round it prints `failed <year> round <round>: <reason>`, writes nothing for that round, continues with the remaining rounds, and exits with code 1.

**Normalized lap schema** (`laps.parquet` columns)

| Column | Type | Source |
|---|---|---|
| `driver` | str (3-letter code) | `Driver` |
| `team` | str | `Team` |
| `lap` | int | `LapNumber` |
| `lap_time_s` | float, nullable | `LapTime` in seconds |
| `session_time_s` | float, nullable | `Time` (session time at lap end) in seconds |
| `stint` | int | `Stint` |
| `compound` | str, nullable | `Compound` |
| `tyre_life` | int, nullable | `TyreLife` |
| `pit_in` | bool | `PitInTime` is not null |
| `pit_out` | bool | `PitOutTime` is not null |
| `track_status` | str | `TrackStatus` |
| `is_accurate` | bool | `IsAccurate` |

**SQLite catalog**

- `races(race_id TEXT PRIMARY KEY, year INT, round INT, event_name TEXT, location TEXT, date TEXT, total_laps INT, ingested_at TEXT)`; `location` is FastF1 `Location` (for example `Sakhir`, `Yas Island`) and lets later changes match the same circuit across seasons.
- `drivers(race_id TEXT, code TEXT, full_name TEXT, team TEXT, team_color TEXT, grid_position INT, PRIMARY KEY (race_id, code))`; `team_color` is FastF1 `TeamColor` as `#RRGGBB`, or `#71717A` when missing.

**HTTP API** (FastAPI app `augur.api:app`, CORS allows `http://localhost:5173`)

- `GET /api/health` → `{"status": "ok"}`
- `GET /api/races` → list of `{race_id, year, round, event_name, date, total_laps}` ordered by year then round.
- `GET /api/races/{race_id}/state?lap=N` → `{race_id, lap, total_laps, track_status, drivers: [...]}`; `track_status` is the leader's `track_status` on its last completed lap; each driver: `{code, team, team_color, position, laps_completed, last_lap_time_s, compound, tyre_age_laps, stint, pit_count, gap_to_leader_s, laps_behind_leader}`; ordered by `position`. `pit_count` is `stint - 1` at the last completed lap. Missing values are JSON `null`.
- `GET /api/races/{race_id}/laps?lap=N[&driver=CODE]` → list of normalized lap rows with `lap <= N`, ordered by driver then lap.
- Errors: unknown race → 404 `{"detail": "race not found"}`; `lap` missing, below 1, or above `total_laps` → 422; unknown `driver` → 404 `{"detail": "driver not found"}`.

**Acceptance**

- `pytest backend` passes offline, including `test_state_unaffected_by_future_laps`, which alters every row with `lap > N` in the fixture and asserts that the `/state` and `/laps` responses at lap N are identical.
- Manual: ingest 2024 rounds 1 and 24, start uvicorn, `curl /api/races/2024-01-bahrain-grand-prix/state?lap=10` returns 20 drivers, and `GET /api/races` lists both races.

**Scope**

- In: backend package skeleton, ingest command, storage, `ReplayStore`, `RaceFeed` and `ReplayFeed`, the four endpoints, tests.
- Out: feature engineering, models, events, frontend (later changes), `LiveFeed` and OpenF1.

## Risks / Trade-offs

- [FastF1 download is slow or rate-limited] → FastF1 cache under `data/fastf1-cache/`; ingest only needed rounds.
- [FastF1 column names change between versions] → pin the installed fastf1 version in `pyproject.toml`; the normalizer test fails loudly on missing columns.
- [Computed position differs from official timing around pit stops] → accepted for the MVP; documented in the README.
