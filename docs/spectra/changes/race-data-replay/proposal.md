## Why

AUGUR has no data yet. Every later feature (lap-time model, event detection, dashboard) needs historical race laps stored locally and a single access path that only exposes laps up to the current replay lap. Building this first makes the no-future-leakage rule structural instead of a convention each feature must remember.

## What Changes

- Add a backend Python package `augur` under `backend/` with a `pyproject.toml`, FastAPI app, and pytest setup.
- Add an ingest command that downloads one or more historical races with FastF1 and stores lap-level data as Parquet plus race metadata in SQLite under `data/`.
- Add a lap-cutoff data access layer: every read of race laps takes a `lap` argument and returns only laps with lap number less than or equal to it.
- Add HTTP endpoints to list ingested races and to return the race state (track status, per-driver position, team colour, last lap time, tyre compound, tyre age, stint, pit count, gap to leader) at a given lap.
- Use 2024 round 1 (Bahrain) and 2024 round 24 (Abu Dhabi, the season finale) as the two demo races.
- Add a `RaceFeed` interface (latest lap, laps up to a lap) with a `ReplayFeed` implementation, so later live data (OpenF1) can replace replay without changing any consumer.
- Add a test that proves the race state at lap N is unchanged when data for laps after N is altered.

## Non-Goals

Recorded in design.md.

## Capabilities

### New Capabilities

- `race-data-ingest`: Download historical races via FastF1 and persist laps (Parquet) and race metadata (SQLite) locally, idempotently.
- `lap-replay-api`: Serve the list of ingested races and the per-driver race state at a requested lap through a `RaceFeed`, reading only laps up to that lap.

### Modified Capabilities

(none)

## Impact

- New code: backend/pyproject.toml, backend/src/augur/ (ingest, storage, replay, api modules), backend/tests/.
- New dependencies: fastf1, pandas, pyarrow, fastapi, uvicorn, pydantic, pytest, httpx.
- New local data directory data/ (git-ignored): FastF1 cache, per-race Parquet files, augur.sqlite.
- Network access to the FastF1 public data source during ingest only; the API itself works offline.
