# AUGUR — F1 Race Intelligence

AUGUR replays historical Formula 1 races lap by lap and serves the race state at any lap through an HTTP API. Nothing served at lap N reads data from laps after N.

## Data source

Race data comes from the public [OpenF1](https://openf1.org) API (historical sessions from 2023 onward). **No account or subscription is needed.** Ingest needs network access; the API and tests run offline afterwards.

Two lap columns are derived because OpenF1 has no per-lap equivalent:

- `track_status` uses FastF1-style codes — `1` green, `2` yellow, `4` safety car, `5` red flag, `6` virtual safety car — and is the most severe status from OpenF1 race control messages active during the lap.
- `is_accurate` is true when the lap has a lap time, is not lap 1, and is neither a pit-in nor a pit-out lap.

Race positions are computed from laps completed and session time at the end of each driver's last lap, so they can differ from official timing around pit stops.

## Setup

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[dev]"
```

On Ubuntu without `python3.X-venv`, create the venv with `python3 -m venv --without-pip backend/.venv` and install pip into it with any other pip: `python -m pip --python backend/.venv/bin/python install pip`.

## Ingest races

```bash
backend/.venv/bin/python -m augur.ingest --year 2024 --rounds 1 24
```

Output, one line per race:

```
ingested 2024-01-bahrain-grand-prix: 20 drivers, 57 laps
ingested 2024-24-abu-dhabi-grand-prix: 20 drivers, 58 laps
```

- Rounds are counted over the year's non-cancelled races in date order.
- Data goes to `data/` at the repository root (override with `--data-dir`): `data/races/<race_id>/laps.parquet`, `data/augur.sqlite`, and the response cache `data/openf1-cache/`.
- Re-running replaces the race. A failed round prints `failed <year> round <round>: <reason>`, stores nothing for that round, and the command exits 1.

## Run the API

```bash
backend/.venv/bin/uvicorn augur.api:app --reload
```

| Endpoint | Returns |
|---|---|
| `GET /api/health` | `{"status": "ok"}` |
| `GET /api/races` | ingested races ordered by year, round |
| `GET /api/races/{race_id}/state?lap=N` | track status and per-driver position, gap, tyre, stint, pit count at lap N |
| `GET /api/races/{race_id}/laps?lap=N[&driver=VER]` | normalized lap rows with lap ≤ N |

```bash
curl "localhost:8000/api/races/2024-01-bahrain-grand-prix/state?lap=10"
```

CORS allows `http://localhost:5173` (the dashboard dev server).

## Test

```bash
backend/.venv/bin/pytest backend                 # offline, a few seconds
backend/.venv/bin/pytest backend --run-network   # also downloads 2024 round 1 from OpenF1
```

`test_state_unaffected_by_future_laps` proves that responses at lap N do not change when laps after N are altered.
