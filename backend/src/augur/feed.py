"""Race feeds: the only way API handlers obtain lap data."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from augur.replay import RaceNotFound, ReplayStore


@runtime_checkable
class RaceFeed(Protocol):
    race_id: str
    total_laps: int

    def latest_lap(self) -> int: ...

    def laps_until(self, lap: int) -> pd.DataFrame: ...


class ReplayFeed:
    """Replays a stored race: every lap is already available."""

    def __init__(self, race_id: str, store: ReplayStore) -> None:
        race = store.get_race(race_id)
        if race is None:
            raise RaceNotFound(race_id)
        self.race_id = race_id
        self.total_laps = int(race["total_laps"])
        self._store = store

    def latest_lap(self) -> int:
        return self.total_laps

    def laps_until(self, lap: int) -> pd.DataFrame:
        return self._store.laps_until(self.race_id, lap)
