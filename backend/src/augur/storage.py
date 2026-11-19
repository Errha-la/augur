"""Write one normalized race to disk: laps.parquet plus catalog rows.

A store is all-or-nothing. The parquet file is written to a temporary file
next to its final path; the races/drivers rows are written in one SQLite
transaction; the temporary file is renamed over the final path only inside
that transaction and the previous file (on re-ingest) is kept as a backup
until the commit succeeds. Any failure rolls back the catalog, removes the
temporary file, and restores the previous parquet file.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from augur import catalog
from augur.schema import LAP_COLUMNS

RACE_ID_RE = re.compile(r"^\d{4}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
TEAM_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class RaceRecord:
    race_id: str
    year: int
    round: int
    event_name: str
    location: str | None
    date: str | None
    total_laps: int


@dataclass(frozen=True)
class DriverRecord:
    code: str
    full_name: str | None
    team: str | None
    team_color: str
    grid_position: int | None


def validate_race_id(race_id: str) -> str:
    """Reject any race_id that is not `<yyyy>-<rr>-<slug>` (path-safe)."""
    if not isinstance(race_id, str) or not RACE_ID_RE.fullmatch(race_id):
        raise ValueError(f"invalid race_id {race_id!r}")
    return race_id


def _validate(race: RaceRecord, drivers: list[DriverRecord], laps: pd.DataFrame) -> None:
    validate_race_id(race.race_id)
    if tuple(laps.columns) != LAP_COLUMNS:
        raise ValueError(
            f"laps columns {list(laps.columns)} do not match LAP_COLUMNS {list(LAP_COLUMNS)}"
        )
    codes = [d.code for d in drivers]
    if len(codes) != len(set(codes)):
        raise ValueError(f"duplicate driver codes for {race.race_id}: {codes}")
    for d in drivers:
        if not TEAM_COLOR_RE.fullmatch(d.team_color):
            raise ValueError(f"invalid team_color {d.team_color!r} for {d.code}")


def store_race(
    data_dir: Path,
    race: RaceRecord,
    drivers: list[DriverRecord],
    laps: pd.DataFrame,
    *,
    ingested_at: str | None = None,
) -> Path:
    """Replace the race's parquet file and catalog rows. Returns the parquet path."""
    _validate(race, drivers, laps)
    data_dir = Path(data_dir)
    final = catalog.laps_path(data_dir, race.race_id)
    final.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    tmp = final.with_name(f".laps.parquet.{token}.tmp")
    backup = final.with_name(f".laps.parquet.{token}.bak")
    ingested_at = ingested_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    conn = catalog.connect(data_dir)
    replaced = False
    had_previous = False
    try:
        laps.reset_index(drop=True).to_parquet(tmp, index=False)
        with conn:  # one transaction; rolls back on exception
            conn.execute("DELETE FROM drivers WHERE race_id = ?", (race.race_id,))
            conn.execute("DELETE FROM races WHERE race_id = ?", (race.race_id,))
            conn.execute(
                "INSERT INTO races (race_id, year, round, event_name, location, date,"
                " total_laps, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    race.race_id,
                    int(race.year),
                    int(race.round),
                    race.event_name,
                    race.location,
                    race.date,
                    int(race.total_laps),
                    ingested_at,
                ),
            )
            conn.executemany(
                "INSERT INTO drivers (race_id, code, full_name, team, team_color,"
                " grid_position) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        race.race_id,
                        d.code,
                        d.full_name,
                        d.team,
                        d.team_color,
                        None if d.grid_position is None else int(d.grid_position),
                    )
                    for d in drivers
                ],
            )
            # Swap files last, still inside the transaction, so a failure here
            # also rolls back the catalog rows.
            if final.exists():
                os.replace(final, backup)
                had_previous = True
            os.replace(tmp, final)
            replaced = True
    except BaseException:
        if replaced:
            # Commit failed after the swap: undo it.
            final.unlink(missing_ok=True)
        if had_previous and backup.exists():
            os.replace(backup, final)
        tmp.unlink(missing_ok=True)
        _remove_if_empty(final.parent)
        raise
    finally:
        conn.close()
    backup.unlink(missing_ok=True)
    return final


def _remove_if_empty(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass
