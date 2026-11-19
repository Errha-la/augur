"""Incremental event engine over a RaceFeed.

``EventEngine.step(lap)`` reads ``feed.laps_until(lap)`` only, so the same
engine runs on a replay (stepping 1..total_laps) or, later, on live data
(stepping each time ``feed.latest_lap()`` grows).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import pandas as pd

from augur import config
from augur.events import detectors
from augur.events.analysis import explain
from augur.feed import RaceFeed
from augur.features import build_feature_table
from augur.models.base import LapTimeModel
from augur.models.degradation import current_stint_degradation
from augur.predictions import predict_lap_times
from augur.state import race_state
from augur.strategy import simulate


class OutOfOrderStep(ValueError):
    pass


def _opt(value) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return float(value)


class EventEngine:
    def __init__(self, feed: RaceFeed, model: LapTimeModel, prior: Mapping[str, float] | None = None) -> None:
        self.feed = feed
        self.model = model
        self.prior = dict(prior or {})
        self.state = detectors.DetectorState()
        self._next_lap = 1

    @property
    def next_lap(self) -> int:
        return self._next_lap

    def step(self, lap: int) -> list[dict]:
        """Events first detected on ``lap``. Laps must be stepped in order from 1."""
        if isinstance(lap, bool) or not isinstance(lap, int) or lap != self._next_lap:
            raise OutOfOrderStep(f"expected lap {self._next_lap}, got {lap}")
        total = self.feed.total_laps
        laps = self.feed.laps_until(lap)
        laps = laps[laps["lap"] <= lap]  # defensive: a feed must never return later laps

        table = build_feature_table(laps, total, self.prior)
        current = table[table["target_lap"] == lap].reset_index(drop=True)
        predicted = predict_lap_times(current, self.model)
        degradation = current_stint_degradation(laps, total)
        lap_rows = laps[laps["lap"] == lap].set_index("driver")

        observations = []
        for i, row in current.iterrows():
            driver = row["driver"]
            tyre_life = lap_rows["tyre_life"].get(driver) if driver in lap_rows.index else None
            observations.append(
                detectors.LapObservation(
                    driver=driver,
                    lap_time_s=_opt(row["target_lap_time_s"]),
                    predicted_s=_opt(predicted.iat[i]),
                    clean=bool(row["target_clean"]),
                    compound=lap_rows["compound"].get(driver) if driver in lap_rows.index else None,
                    tyre_life=None if tyre_life is None or pd.isna(tyre_life) else int(tyre_life),
                )
            )

        standings = race_state(laps, [], {"race_id": self.feed.race_id, "total_laps": total}, lap)
        positions = {d["code"]: d["position"] for d in standings["drivers"]}

        cars = self._cars(laps, standings["drivers"], degradation)
        stopped = laps["pit_in"].astype(bool) | laps["pit_out"].astype(bool)
        pit_drivers = sorted(set(laps.loc[(laps["lap"] == lap) & stopped, "driver"]))

        events = []
        events += detectors.detect_pace_drop(lap, observations, self.state)
        events += detectors.detect_degradation(lap, degradation, self.state)
        events += detectors.detect_undercut(lap, cars, self.state)
        events += detectors.detect_position_change(lap, positions, self.state, total, pitted=pit_drivers)
        for e in events:
            if e["type"] == "position_change":
                e["evidence"]["pit_drivers"] = pit_drivers
            elif e["type"] in ("degradation_warning", "undercut_window"):
                e["evidence"]["strategy"] = self._best_strategy(laps, e["drivers"][0], lap)
        self._next_lap += 1
        return [self._finish(e) for e in events]

    def _best_strategy(self, laps, driver: str, lap: int) -> dict | None:
        """Fastest-on-average strategy for ``driver`` at ``lap`` (seeded, reproducible)."""
        result = simulate(
            laps,
            self.feed.total_laps,
            driver,
            lap,
            runs=config.STRATEGY_RUNS_DEFAULT,
            seed=config.STRATEGY_SEED_DEFAULT,
        )
        if not result["strategies"]:
            return None
        best = result["strategies"][0]
        return {k: best[k] for k in ("name", "pit_lap", "mean_s", "win_probability")}

    @staticmethod
    def _cars(laps, standings: list[dict], degradation: Mapping[str, dict]) -> list[detectors.CarStatus]:
        window = config.UNDERCUT_NO_PIT_LAPS
        pits = laps[laps["pit_in"].astype(bool) | laps["pit_out"].astype(bool)]
        pit_laps: dict[str, list[int]] = {}
        for driver, lap_no in zip(pits["driver"], pits["lap"]):
            pit_laps.setdefault(driver, []).append(int(lap_no))
        session = {(d, int(n)): t for d, n, t in zip(laps["driver"], laps["lap"], laps["session_time_s"])}
        cars = []
        for d in standings:
            done = d["laps_completed"]
            if done < 1:
                continue
            code = d["code"]
            cars.append(
                detectors.CarStatus(
                    driver=code,
                    position=d["position"],
                    laps_completed=done,
                    session_time_s=_opt(session.get((code, done))),
                    stint=d["stint"],
                    compound=d["compound"],
                    tyre_life=d["tyre_age_laps"],
                    pitted_recently=any(done - window < p <= done for p in pit_laps.get(code, ())),
                    deg_s_per_lap=degradation.get(code, {}).get("deg_s_per_lap"),
                )
            )
        return cars

    def _finish(self, event: dict) -> dict:
        event_id = f"{self.feed.race_id}:{event['lap']}:{event['type']}:{'-'.join(event['drivers'])}"
        title, analysis = explain(event)
        return {
            "id": event_id,
            "lap": event["lap"],
            "type": event["type"],
            "drivers": event["drivers"],
            "severity": event["severity"],
            "title": title,
            "analysis": analysis,
            "evidence": event["evidence"],
        }
