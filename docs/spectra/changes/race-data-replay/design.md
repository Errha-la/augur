## Context

The repository is empty apart from Spectra and agent instructions. AUGUR is a 2-day portfolio build: FastAPI backend in `backend/`, React dashboard in `frontend/` (later change). This change creates the data foundation that the `prediction-and-events` and `race-dashboard` changes build on. OpenF1 is the only data source. The project rule is that nothing computed at replay lap N may read laps after N.

## Goals / Non-Goals

**Goals:**

- One command ingests one or more historical races into `data/` and can be re-run safely.
- One read path for lap data that always takes a lap cutoff.
- HTTP endpoints for the race list, race state at lap N, and lap history up to lap N.
- Tests run offline in seconds.
- Anyone who clones the repository can ingest data without an account or subscription.

**Non-Goals:**

- Car telemetry (speed, throttle, GPS traces). Lap-level data is enough for the MVP models and charts.
- Live timing (`LiveFeed`). Only historical OpenF1 sessions are ingested here.
- Final race classification in any API response, because it is future information during replay. OpenF1 `session_result` is never requested.
- Retirement detection. A driver who stops completing laps shows a growing `laps_behind_leader`.
- Grid positions. OpenF1 `starting_grid` returned HTTP 404 for 2024 round 1 (measured), so `drivers.grid_position` stays null.
- Authentication, deployment, database servers.

**Demo races:** 2024 round 1 `2024-01-bahrain-grand-prix` and 2024 round 24 `2024-24-abu-dhabi-grand-prix` (season finale). Both are also the fixed benchmark races used by later changes.

## Decisions

### OpenF1 REST API as the data source

Ingest reads the public OpenF1 API (`https://api.openf1.org/v1`) with `urllib.request`: endpoints `sessions`, `meetings`, `drivers`, `laps`, `stints`, `pit`, and `race_control`, each filtered by `session_key` (or by `year` for `sessions` and `meetings`). No account is needed for historical sessions (2023 onward). Raw JSON responses are cached under `data/openf1-cache/`, so a re-ingest does not hit the network again. Alternatives considered: FastF1 (rejected, see Supersedes below); Jolpica/Ergast (rejected because it has no tyre compound or stint data).

**Supersedes:** "Lap-level data only, no car telemetry" through FastF1 (`laps=True, telemetry=False, weather=False, messages=False`, cache in `data/fastf1-cache/`). FastF1 3.9.2 needs an F1TV subscription for timing data: without `F1_USERNAME`/`F1_PASSWORD` the livetiming server returns HTTP 401 and `session.laps` raises `DataNotLoadedError` (reproduced on 2024 round 1). The project must work without a paid account, so OpenF1 replaces FastF1 and `fastf1` is removed from the dependencies. The lap-level scope (no telemetry) is unchanged.

### Round numbers from the race calendar

OpenF1 sessions carry no round number. Round R of a year is the R-th session, ordered by `date_start`, among `sessions?year=<year>&session_name=Race` entries with `is_cancelled` false. Measured: 2023 has 23 race sessions, 1 cancelled, so 22 rounds, and round 11 is Budapest; 2024 has 24 rounds, round 1 is Sakhir and round 24 is Yas Island. The event name is the `meeting_name` of the session's meeting from `meetings?year=<year>` (for example "Bahrain Grand Prix").

### Derived track status and accuracy

OpenF1 has no per-lap track status or accuracy flag, while later changes (`prediction-and-events`) select clean laps with `track_status == "1"` and `is_accurate`. Both columns are derived so the normalized schema keeps FastF1 semantics:

- `track_status` uses FastF1 codes: `"1"` green, `"2"` yellow, `"4"` safety car, `"5"` red flag, `"6"` virtual safety car. For each lap row, the code is the most severe status active at any time in the lap window `[date_start, date_start + lap_duration]`, with severity `5 > 4 > 6 > 2 > 1`. When the window is unknown (missing `date_start` or `lap_duration`), `track_status` is null.
- `is_accurate` is true when `lap_duration` is present, `lap > 1`, and the lap is neither a pit-in nor a pit-out lap. This approximates FastF1 `IsAccurate`; it is not identical.

### Parquet per race plus SQLite catalog

Each race is stored as `data/races/<race_id>/laps.parquet`. A SQLite file `data/augur.sqlite` holds the `races` and `drivers` tables. Alternative: everything in SQLite. Rejected because Parquet loads straight into pandas for the model work in the next change, and SQLite stays a small catalog. `race_id` format is `<year>-<round two digits>-<slug of event name>`, for example `2024-01-bahrain-grand-prix`.

### Single cutoff read path

`augur.replay.ReplayStore` is the only module that reads `laps.parquet` for serving. Its public read method is `laps_until(race_id, lap)`, which filters `lap <= cutoff` before returning a copy. API handlers and later model code call it and never read Parquet directly. Alternative: filter in each endpoint. Rejected because one missed filter leaks future data silently.

### Race feed interface for replay now and live later

AUGUR will later run on live timing for viewers, so every consumer (API, models, event engine) reads race data through a `RaceFeed` protocol: `race_id`, `total_laps`, `latest_lap() -> int`, and `laps_until(lap) -> DataFrame`. `ReplayFeed(race_id, store)` implements it over `ReplayStore`, with `latest_lap()` returning `total_laps`. A future `LiveFeed` implements the same protocol from OpenF1; it is out of scope here. Alternative: call `ReplayStore` directly everywhere. Rejected because switching to live would touch every consumer.

### Computed positions from laps completed and session time

Race state position is computed as the rank by (laps completed descending, session time at end of last completed lap ascending). Gap to leader is the driver's session time at their last completed lap L minus the leader's session time at lap L.

### Offline tests with synthetic fixtures

Tests build a small synthetic laps table (3 drivers, 5 laps) in the normalized schema and fake OpenF1 JSON payloads for the normalizer and the ingest command. A single real-download smoke test is marked `network` and skipped by default.

## Implementation Contract

**Ingest command**

- Invocation: `python -m augur.ingest --year 2024 --rounds 1 [2 3 ...]` (run with the package installed). Default data root is `data/` at the repository root; override with `--data-dir`.
- For each round it resolves the OpenF1 race session (see "Round numbers from the race calendar"), downloads the endpoints listed under "OpenF1 REST API as the data source", normalizes laps, writes `laps.parquet`, and upserts one `races` row and one `drivers` row per driver.
- Response cache: `<data_dir>/openf1-cache/<year>/race-sessions.json` (the year's `sessions` request always filters `session_name=Race`, so this file holds only Race sessions), `<data_dir>/openf1-cache/<year>/meetings.json`, and `<data_dir>/openf1-cache/<session_key>/<endpoint>.json`. A cached file is used instead of a request. Year-level requests take no other filters, so one cache file always corresponds to one query.
- Empty results: OpenF1 answers a query with no rows with HTTP 404 and body `{"detail": "No results found."}`. The client returns an empty list for that response and caches it like an HTTP 200 list. Any other 404 fails the round. Whether an empty list is fatal is decided after loading: no race session for the round fails with `no race session for round <round>` (this also covers a year without OpenF1 data), no laps or no drivers fails the round, and empty `pit`, `stints`, or `race_control` lists are allowed.
- HTTP: at most 3 requests per second (the OpenF1 free-tier limit as stated in the OpenF1 docs; not measured here); on HTTP 429 or 5xx, retry up to 3 times with 2, 4, and 8 s waits, then fail the round; request timeout 60 s. The session loader is injectable so tests run without network.
- Prints one line per race: `ingested <race_id>: <n_drivers> drivers, <n_laps> laps`. Exit code 0 when all rounds succeed.
- On any failure for a round it prints `failed <year> round <round>: <reason>`, writes nothing under `races/` or in the catalog for that round, continues with the remaining rounds, and exits with code 1. A round beyond the year's calendar fails with reason `no race session for round <round>`.

**Normalized lap schema** (`laps.parquet` columns)

| Column | Type | OpenF1 source |
|---|---|---|
| `driver` | str (3-letter code) | `drivers.name_acronym` joined on `driver_number` |
| `team` | str | `drivers.team_name` |
| `lap` | int | `laps.lap_number` |
| `lap_time_s` | float, nullable | `laps.lap_duration` |
| `session_time_s` | float, nullable | (`laps.date_start` + `lap_duration`) minus the race session `date_start`, in seconds |
| `stint` | int, nullable | `stints.stint_number` of the driver's stint with `lap_start <= lap <= lap_end` |
| `compound` | str, nullable | `stints.compound`; `UNKNOWN` or missing → null |
| `tyre_life` | int, nullable | `stints.tyre_age_at_start + (lap - lap_start) + 1` |
| `pit_in` | bool | a `pit` row exists for the driver with this `lap_number` (OpenF1 records the in-lap: measured VER 2024 R1 pit laps 17, 37 and pit-out laps 18, 38) |
| `pit_out` | bool | `laps.is_pit_out_lap` |
| `track_status` | str, nullable | derived from `race_control` (see below) |
| `is_accurate` | bool | derived (see "Derived track status and accuracy") |

`track_status` derivation from `race_control` messages, processed in `date` order:

| Message | Effect |
|---|---|
| category `Flag`, flag `RED`, scope `Track` | red flag starts |
| category `SafetyCar`, message contains `VIRTUAL SAFETY CAR DEPLOYED` | VSC starts |
| category `SafetyCar`, message contains `VIRTUAL SAFETY CAR ENDING` | VSC ends |
| category `SafetyCar`, message contains `SAFETY CAR DEPLOYED` and not `VIRTUAL` | safety car starts |
| category `Flag`, flag `YELLOW` or `DOUBLE YELLOW`, scope `Sector` | yellow starts in that sector |
| category `Flag`, flag `CLEAR`, scope `Sector` | yellow ends in that sector |
| category `Flag`, flag `GREEN` or `CLEAR`, scope `Track` | red flag, safety car, and all sector yellows end |

**SQLite catalog**

- `races(race_id TEXT PRIMARY KEY, year INT, round INT, event_name TEXT, location TEXT, date TEXT, total_laps INT, ingested_at TEXT)`; `location` is the OpenF1 session `location` (for example `Sakhir`, `Yas Island`) and lets later changes match the same circuit across seasons. `date` is the UTC calendar date of the session `date_start` as `YYYY-MM-DD`; a night race that starts after UTC midnight shows the next day (for example the 2024 Las Vegas GP, 23 Nov local, is `2024-11-24`). `total_laps` is the highest `lap_number` in `laps`.
- `drivers(race_id TEXT, code TEXT, full_name TEXT, team TEXT, team_color TEXT, grid_position INT, PRIMARY KEY (race_id, code))`; `code` is `name_acronym`, `full_name` is OpenF1 `full_name`, `team_color` is `#` + OpenF1 `team_colour` as `#RRGGBB`, or `#71717A` when missing; `grid_position` is null.

**HTTP API** (FastAPI app `augur.api:app`, CORS allows `http://localhost:5173`)

- `GET /api/health` → `{"status": "ok"}`
- `GET /api/races` → list of `{race_id, year, round, event_name, date, total_laps}` ordered by year then round.
- `GET /api/races/{race_id}/state?lap=N` → `{race_id, lap, total_laps, track_status, drivers: [...]}`; `track_status` is the leader's `track_status` on its last completed lap; each driver: `{code, team, team_color, position, laps_completed, last_lap_time_s, compound, tyre_age_laps, stint, pit_count, gap_to_leader_s, laps_behind_leader}`; ordered by `position`. `pit_count` is `stint - 1` at the last completed lap. Missing values are JSON `null`.
- `GET /api/races/{race_id}/laps?lap=N[&driver=CODE]` → list of normalized lap rows with `lap <= N`, ordered by driver then lap.
- Errors: unknown race → 404 `{"detail": "race not found"}`; `lap` missing, below 1, or above `total_laps` → 422; unknown `driver` → 404 `{"detail": "driver not found"}`.

**Acceptance**

- `pytest backend` passes offline, including `test_state_unaffected_by_future_laps`, which alters every row with `lap > N` in the fixture and asserts that the `/state` and `/laps` responses at lap N are identical.
- `pip install -e "backend[dev]"` does not install `fastf1`, and `grep -ri fastf1 backend/src` finds nothing.
- Manual: ingest 2024 rounds 1 and 24, start uvicorn, `curl /api/races/2024-01-bahrain-grand-prix/state?lap=10` returns 20 drivers, and `GET /api/races` lists both races.

**Scope**

- In: backend package skeleton, OpenF1 client and ingest command, storage, `ReplayStore`, `RaceFeed` and `ReplayFeed`, the four endpoints, tests, and the FastF1 → OpenF1 wording in AGENTS.md and docs/spectra/config.yaml.
- Out: feature engineering, models, events, frontend (later changes), `LiveFeed`, grid positions, telemetry.

## Risks / Trade-offs

- [OpenF1 rate limit or downtime] → request throttle, bounded retries, and the response cache under `data/openf1-cache/`; ingest only needed rounds.
- [OpenF1 response fields change] → the normalizer raises `KeyError` naming the missing fields; fake-payload tests fail loudly.
- [Derived `track_status` and `is_accurate` differ from FastF1 values] → accepted for the MVP; the derivation rules are listed above and in the README.
- [Computed position differs from official timing around pit stops] → accepted for the MVP; documented in the README.
