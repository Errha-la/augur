"""HTTP API for replaying ingested races lap by lap.

Lap data reaches handlers only through a RaceFeed; the ReplayStore is used
here for catalog lookups (race list, drivers, team colours) only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from augur import catalog, config
from augur import wrapped as wrapped_content
from augur.feed import RaceFeed, ReplayFeed
from augur.models import registry
from augur.models.base import LapTimeModel
from augur.narration.serving import serving_key
from augur.predictions import predictions_at
from augur.priors import circuit_priors
from augur.strategy import simulate
from augur.replay import RaceNotFound, ReplayStore
from augur.schema import LAP_COLUMNS
from augur.state import race_state, to_json_value

ALLOWED_ORIGINS = ["http://localhost:5173"]
# Prepared Wrapped races kept in memory (oldest dropped first).
WRAPPED_CACHE_SIZE = 8

# Response fields of /positions and /positions/history (design.md API contract;
# the race-dashboard mocks follow the same shapes).
POSITION_FIELDS = (
    "code", "p_win", "p_podium", "p_points", "expected_position", "position_p10", "position_p90",
)
POSITION_HISTORY_FIELDS = ("code", "p_win", "p_podium", "expected_position")

LapParam = Annotated[int, Query(ge=1, description="Replay cutoff lap (1..total_laps)")]
RunsParam = Annotated[
    int, Query(ge=config.STRATEGY_RUNS_MIN, le=config.STRATEGY_RUNS_MAX, description="Monte Carlo runs")
]
SeedParam = Annotated[int, Query(ge=0, le=2**32 - 1, description="Random seed")]


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

    model_cache: dict[tuple[str, int], LapTimeModel] = {}
    prior_cache: dict[tuple, dict[str, float]] = {}
    wrapped_cache: dict[tuple, wrapped_content.Prepared] = {}

    def priors_for(s: ReplayStore, race_id: str) -> dict[str, float]:
        """circuit_priors, cached per race until the prior race is re-ingested."""
        prior_id = s.find_prior_race(race_id)
        if prior_id is None:
            return {}
        key = (str(s.data_dir), race_id, prior_id, s.ingested_at(prior_id))
        if key not in prior_cache:
            prior_cache[key] = circuit_priors(s, race_id)
        return prior_cache[key]

    def model_name() -> str:
        name = os.environ.get(config.MODEL_ENV) or config.DEFAULT_MODEL
        try:
            registry.get_model_class(name)
        except registry.UnknownModelError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
        return name

    def served_model(s: ReplayStore) -> LapTimeModel:
        name = model_name()
        path = registry.model_path(s.data_dir, name)
        try:
            key = (str(path), path.stat().st_mtime_ns)
        except FileNotFoundError:
            raise HTTPException(
                status_code=503, detail=str(registry.ModelNotTrainedError(name))
            ) from None
        if key not in model_cache:
            model_cache.clear()
            model_cache[key] = registry.load_trained(s.data_dir, name)
        return model_cache[key]

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

    @app.get("/api/races/{race_id}/predictions")
    def predictions(race_id: str, lap: LapParam) -> dict:
        s = store()
        feed = open_feed(s, race_id, lap)
        model = served_model(s)
        drivers = predictions_at(
            feed.laps_until(lap),
            feed.total_laps,
            lap,
            model,
            priors_for(s, race_id),
            [d["code"] for d in s.list_drivers(race_id)],
        )
        return {"race_id": feed.race_id, "lap": lap, "drivers": drivers}

    @app.get("/api/races/{race_id}/events")
    def events(race_id: str, lap: LapParam) -> dict:
        s = store()
        feed = open_feed(s, race_id, lap)
        name = model_name()
        analyzed = s.is_analyzed(race_id, name)
        events = s.events_until(race_id, name, lap) if analyzed else []
        # Commentary cached by augur.narrate for the current narrator settings; never generated here.
        key = serving_key(name)
        texts = s.commentary_texts([e["id"] for e in events], key) if key is not None else {}
        for e in events:
            e["commentary"] = texts.get(e["id"])
        return {
            "race_id": feed.race_id,
            "lap": lap,
            "model": name,
            "analyzed": analyzed,
            "commentary_model": key.llm_model if key is not None else None,
            "events": events,
        }

    @app.get("/api/races/{race_id}/positions")
    def positions(race_id: str, lap: LapParam) -> dict:
        s = store()
        feed = open_feed(s, race_id, lap)
        name = model_name()
        analyzed = s.has_positions(race_id, name)
        rows = s.positions_until(race_id, name, lap, only_lap=True) if analyzed else []
        return {
            "race_id": feed.race_id,
            "lap": lap,
            "model": name,
            "analyzed": analyzed,
            "runs": rows[0]["runs"] if rows else None,
            "seed": rows[0]["seed"] if rows else None,
            "drivers": [{k: r[k] for k in POSITION_FIELDS} for r in rows],
        }

    @app.get("/api/races/{race_id}/positions/history")
    def positions_history(race_id: str, lap: LapParam) -> dict:
        s = store()
        feed = open_feed(s, race_id, lap)
        name = model_name()
        analyzed = s.has_positions(race_id, name)
        by_lap: dict[int, list[dict]] = {}
        for r in s.positions_until(race_id, name, lap) if analyzed else []:
            by_lap.setdefault(r["lap"], []).append({k: r[k] for k in POSITION_HISTORY_FIELDS})
        return {
            "race_id": feed.race_id,
            "model": name,
            "analyzed": analyzed,
            "laps": [{"lap": n, "drivers": drivers} for n, drivers in sorted(by_lap.items())],
        }

    @app.get("/api/races/{race_id}/wrapped")
    def wrapped(race_id: str, lap: LapParam, driver: str) -> dict:
        s = store()
        feed = open_feed(s, race_id, lap)
        if driver not in {d["code"] for d in s.list_drivers(race_id)}:
            raise HTTPException(status_code=404, detail="driver not found")
        # The Wrapped reads the whole race, so it must never open before the flag.
        if lap < feed.total_laps:
            raise HTTPException(status_code=409, detail="wrapped unlocks at the final lap")
        name = model_name()
        if not s.is_analyzed(race_id, name) or not s.has_positions(race_id, name):
            raise HTTPException(status_code=409, detail="race not analyzed")
        model = served_model(s)  # 503 when untrained; cached across requests
        path = registry.model_path(s.data_dir, name)
        # The driver-independent part (orders, scores, events) is the same for every
        # driver; rebuild it only when the race is re-ingested or re-analyzed, or the model changes.
        key = (
            str(s.data_dir), race_id, name, path.stat().st_mtime_ns,
            s.analyzed_at(race_id, name), s.ingested_at(race_id),
        )
        if key not in wrapped_cache:
            if len(wrapped_cache) >= WRAPPED_CACHE_SIZE:
                wrapped_cache.pop(next(iter(wrapped_cache)))
            wrapped_cache[key] = wrapped_content.prepare(s.data_dir, race_id, name, model=model)
        return wrapped_content.build(wrapped_cache[key], driver)

    @app.get("/api/races/{race_id}/strategy")
    def strategy(
        race_id: str,
        lap: LapParam,
        driver: str,
        runs: RunsParam = config.STRATEGY_RUNS_DEFAULT,
        seed: SeedParam = config.STRATEGY_SEED_DEFAULT,
    ) -> dict:
        s = store()
        feed = open_feed(s, race_id, lap)
        if driver not in {d["code"] for d in s.list_drivers(race_id)}:
            raise HTTPException(status_code=404, detail="driver not found")
        result = simulate(feed.laps_until(lap), feed.total_laps, driver, lap, runs=runs, seed=seed)
        return {
            "race_id": feed.race_id,
            "lap": lap,
            "driver": driver,
            "runs": runs,
            "seed": seed,
            "pit_loss_s": result["pit_loss_s"],
            "strategies": result["strategies"],
        }

    return app


app = create_app()
