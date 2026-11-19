"""HTTP API for replaying ingested races lap by lap.

Lap data reaches handlers only through a RaceFeed; the ReplayStore is used
here for catalog lookups (race list, drivers, team colours) only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from augur import catalog
from augur.feed import RaceFeed, ReplayFeed
from augur.replay import RaceNotFound, ReplayStore
from augur.schema import LAP_COLUMNS
from augur.state import race_state, to_json_value

ALLOWED_ORIGINS = ["http://localhost:5173"]

LapParam = Annotated[int, Query(ge=1, description="Replay cutoff lap (1..total_laps)")]


def create_app(data_dir: Path | str | None = None) -> FastAPI:
    app = FastAPI(title="AUGUR")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET"],
        allow_headers=[],
    )

    def store() -> ReplayStore:
        # Resolved per request so AUGUR_DATA_DIR is honoured at runtime.
        return ReplayStore(data_dir if data_dir is not None else catalog.default_data_dir())

    def open_feed(s: ReplayStore, race_id: str, lap: int) -> RaceFeed:
        try:
            feed = ReplayFeed(race_id, s)
        except RaceNotFound:
            raise HTTPException(status_code=404, detail="race not found") from None
        if lap > feed.total_laps:
            raise HTTPException(
                status_code=422,
                detail=[
                    {
                        "type": "less_than_equal",
                        "loc": ["query", "lap"],
                        "msg": f"Input should be less than or equal to {feed.total_laps}",
                        "input": lap,
                    }
                ],
            )
        return feed

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/races")
    def races() -> list[dict]:
        return store().list_races()

    @app.get("/api/races/{race_id}/state")
    def state(race_id: str, lap: LapParam) -> dict:
        s = store()
        feed = open_feed(s, race_id, lap)
        laps = feed.laps_until(lap)
        meta = {"race_id": feed.race_id, "total_laps": feed.total_laps}
        return race_state(laps, s.list_drivers(race_id), meta, lap)

    @app.get("/api/races/{race_id}/laps")
    def laps(race_id: str, lap: LapParam, driver: str | None = None) -> list[dict]:
        s = store()
        feed = open_feed(s, race_id, lap)
        if driver is not None and driver not in {d["code"] for d in s.list_drivers(race_id)}:
            raise HTTPException(status_code=404, detail="driver not found")
        df = feed.laps_until(lap)
        if driver is not None:
            df = df[df["driver"] == driver]
        df = df.sort_values(["driver", "lap"], kind="stable")
        cols = list(LAP_COLUMNS)
        return [
            {c: to_json_value(v) for c, v in zip(cols, row)}
            for row in df[cols].itertuples(index=False, name=None)
        ]

    return app


app = create_app()
