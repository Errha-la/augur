## Why

AUGUR has no data yet. Every later feature (lap-time model, event detection, dashboard) needs historical race laps stored locally and a single access path that only exposes laps up to the current replay lap. Building this first makes the no-future-leakage rule structural instead of a convention each feature must remember.

The data source is OpenF1 (`https://api.openf1.org/v1`), which serves historical sessions from 2023 onward for free and without an account. FastF1 3.9.2 was the original source, but its timing data now needs an F1TV subscription (HTTP 401 without `F1_USERNAME`/`F1_PASSWORD`), and AUGUR must stay runnable by anyone who clones it.

## What Changes

- Add a backend Python package `augur` under `backend/` with a `pyproject.toml`, FastAPI app, and pytest setup.
- Add an ingest command that downloads one or more historical races from the OpenF1 REST API and stores lap-level data as Parquet plus race metadata in SQLite under `data/`.
- Keep a source-independent normalized lap schema (12 columns), so replay, API, and later model code do not depend on the data source. `track_status` and `is_accurate` are derived from OpenF1 data because OpenF1 has no per-lap equivalent.
- Add a lap-cutoff data access layer: every read of race laps takes a `lap` argument and returns only laps with lap number less than or equal to it.
- Add HTTP endpoints to list ingested races and to return the race state (track status, per-driver position, team colour, last lap time, tyre compound, tyre age, stint, pit count, gap to leader) at a given lap.
- Use 2024 round 1 (Bahrain) and 2024 round 24 (Abu Dhabi, the season finale) as the two demo races.
- Add a `RaceFeed` interface (latest lap, laps up to a lap) with a `ReplayFeed` implementation, so later live data (OpenF1) can replace replay without changing any consumer.
- Add a test that proves the race state at lap N is unchanged when data for laps after N is altered.
- Remove the FastF1 ingest path and the `fastf1` dependency.

## Non-Goals

Recorded in design.md.

## Capabilities

### New Capabilities

- `race-data-ingest`: Download historical races from OpenF1 and persist laps (Parquet) and race metadata (SQLite) locally, idempotently.
- `lap-replay-api`: Serve the list of ingested races and the per-driver race state at a requested lap through a `RaceFeed`, reading only laps up to that lap.

### Modified Capabilities

(none)

## Impact

- New code: backend/pyproject.toml, backend/src/augur/ (ingest, openf1, storage, replay, feed, state, api modules), backend/tests/.
- Dependencies: pandas, pyarrow, fastapi, uvicorn, pydantic, pytest, httpx. HTTP calls to OpenF1 use the Python standard library (`urllib.request`); no new runtime dependency. `fastf1` is removed.
- New local data directory data/ (git-ignored): OpenF1 response cache, per-race Parquet files, augur.sqlite.
- Network access to the public OpenF1 API during ingest only; the API itself works offline.
- Project rules: AGENTS.md and docs/spectra/config.yaml change "Public data only (FastF1)" to OpenF1.
