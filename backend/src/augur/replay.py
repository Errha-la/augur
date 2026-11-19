"""ReplayStore: the only module that reads stored laps for serving.

Lap data leaves this module only through ``laps_until``, which filters to
``lap <= cutoff`` so callers cannot see future laps. Catalog lookups
(races, drivers) are read-only and never create the catalog file.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from augur import catalog
from augur.schema import LAP_COLUMNS

RACE_FIELDS = ("race_id", "year", "round", "event_name", "date", "total_laps")


class RaceNotFound(LookupError):
    """The race_id is not in the catalog."""


class ReplayStore:
    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)

    # -- catalog -----------------------------------------------------------

    def _connect(self) -> sqlite3.Connection | None:
        path = catalog.db_path(self.data_dir)
        if not path.is_file():
            return None
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        conn = self._connect()
        if conn is None:
            return []
        with closing(conn):
            try:
                return conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError as exc:
                # Catalog file exists but tables were never created.
                if "no such table" in str(exc):
                    return []
                raise

    def list_races(self) -> list[dict]:
        rows = self._query(
            f"SELECT {', '.join(RACE_FIELDS)} FROM races ORDER BY year, round, race_id"
        )
        return [dict(r) for r in rows]

    def get_race(self, race_id: str) -> dict | None:
        if not isinstance(race_id, str):
            raise TypeError("race_id must be a str")
        rows = self._query(
            f"SELECT {', '.join(RACE_FIELDS)} FROM races WHERE race_id = ?", (race_id,)
        )
        return dict(rows[0]) if rows else None

    def race_id_for(self, year: int, round_: int) -> str | None:
        rows = self._query(
            "SELECT race_id FROM races WHERE year = ? AND round = ?", (int(year), int(round_))
        )
        return rows[0]["race_id"] if rows else None

    def find_prior_race(self, race_id: str) -> str | None:
        """The most recent earlier season's race at the same location, if ingested."""
        rows = self._query(
            "SELECT p.race_id FROM races r JOIN races p"
            " ON p.location = r.location AND p.year < r.year"
            " WHERE r.race_id = ? AND r.location IS NOT NULL"
            " ORDER BY p.year DESC, p.round DESC LIMIT 1",
            (race_id,),
        )
        return rows[0]["race_id"] if rows else None

    def ingested_at(self, race_id: str) -> str | None:
        """When the race was last ingested; changes on every re-ingest."""
        rows = self._query("SELECT ingested_at FROM races WHERE race_id = ?", (race_id,))
        return rows[0]["ingested_at"] if rows else None

    def is_analyzed(self, race_id: str, model: str) -> bool:
        rows = self._query(
            "SELECT 1 FROM analyses WHERE race_id = ? AND model = ?", (race_id, model)
        )
        return bool(rows)

    def events_until(self, race_id: str, model: str, lap: int) -> list[dict]:
        """Stored events with ``lap <= lap``, newest lap first, then by severity."""
        rows = self._query(
            "SELECT id, lap, type, drivers, severity, title, analysis, evidence FROM events"
            " WHERE race_id = ? AND model = ? AND lap <= ?"
            " ORDER BY lap DESC, severity DESC, id",
            (race_id, model, int(lap)),
        )
        return [
            {
                "id": r["id"],
                "lap": r["lap"],
                "type": r["type"],
                "drivers": json.loads(r["drivers"]),
                "severity": r["severity"],
                "title": r["title"],
                "analysis": json.loads(r["analysis"]),
                "evidence": json.loads(r["evidence"]),
            }
            for r in rows
        ]

    def list_drivers(self, race_id: str) -> list[dict]:
        rows = self._query(
            "SELECT code, full_name, team, team_color, grid_position "
            "FROM drivers WHERE race_id = ? ORDER BY code",
            (race_id,),
        )
        return [dict(r) for r in rows]

    # -- lap data ----------------------------------------------------------

    def laps_until(self, race_id: str, lap: int) -> pd.DataFrame:
        """Rows of the race with ``lap <= lap`` (a fresh copy, re-read per call)."""
        if isinstance(lap, bool) or not isinstance(lap, int):
            raise TypeError("lap must be an int")
        # race_id is only trusted after a catalog hit; never build a path from it before.
        if self.get_race(race_id) is None:
            raise RaceNotFound(race_id)
        races_root = (self.data_dir / "races").resolve()
        path = catalog.laps_path(self.data_dir, race_id).resolve()
        if path.parent.parent != races_root:
            raise ValueError(f"race_id resolves outside the races directory: {race_id!r}")
        laps = pd.read_parquet(path)
        missing = set(LAP_COLUMNS) - set(laps.columns)
        if missing:
            raise ValueError(f"{path} is missing columns: {sorted(missing)}")
        return laps.loc[laps["lap"] <= lap, list(LAP_COLUMNS)].reset_index(drop=True).copy()
