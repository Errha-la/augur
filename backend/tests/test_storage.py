import sqlite3

import pandas as pd
import pytest

from augur import catalog, storage
from augur.schema import LAP_COLUMNS
from augur.storage import DriverRecord, RaceRecord, store_race

RACE_ID = "2024-01-bahrain-grand-prix"


def laps_df(n_laps=3):
    rows = []
    for code in ("VER", "PER"):
        for lap in range(1, n_laps + 1):
            rows.append(
                {
                    "driver": code, "team": "Red Bull Racing", "lap": lap,
                    "lap_time_s": 95.0 + lap, "session_time_s": 3000.0 + 95 * lap,
                    "stint": 1, "compound": "SOFT", "tyre_life": lap,
                    "pit_in": False, "pit_out": False, "track_status": "1", "is_accurate": True,
                }
            )
    df = pd.DataFrame(rows)
    df["stint"] = df["stint"].astype("Int64")
    df["tyre_life"] = df["tyre_life"].astype("Int64")
    return df.loc[:, list(LAP_COLUMNS)]


def race(total_laps=3, race_id=RACE_ID):
    return RaceRecord(race_id, 2024, 1, "Bahrain Grand Prix", "Sakhir", "2024-03-02", total_laps)


DRIVERS = [
    DriverRecord("VER", "Max Verstappen", "Red Bull Racing", "#3671C6", 1),
    DriverRecord("PER", "Sergio Perez", "Red Bull Racing", "#3671C6", 5),
]


def rows(data_dir, sql, params=()):
    with sqlite3.connect(catalog.db_path(data_dir)) as conn:
        return conn.execute(sql, params).fetchall()


def test_store_writes_parquet_and_catalog(tmp_path):
    path = store_race(tmp_path, race(), DRIVERS, laps_df())
    assert path == catalog.laps_path(tmp_path, RACE_ID)
    back = pd.read_parquet(path)
    assert tuple(back.columns) == LAP_COLUMNS
    assert len(back) == 6
    (r,) = rows(tmp_path, "SELECT race_id, location, total_laps, ingested_at FROM races")
    assert r[:3] == (RACE_ID, "Sakhir", 3) and r[3]
    assert rows(tmp_path, "SELECT code, team_color, grid_position FROM drivers ORDER BY code") == [
        ("PER", "#3671C6", 5), ("VER", "#3671C6", 1)
    ]
    # no temp files left behind
    assert sorted(p.name for p in path.parent.iterdir()) == ["laps.parquet"]


def test_null_lap_time_round_trips_as_null(tmp_path):
    df = laps_df()
    df.loc[0, "lap_time_s"] = float("nan")
    back = pd.read_parquet(store_race(tmp_path, race(), DRIVERS, df))
    assert pd.isna(back.loc[0, "lap_time_s"])


def test_store_same_race_twice_is_idempotent(tmp_path):
    store_race(tmp_path, race(), DRIVERS, laps_df())
    store_race(tmp_path, race(total_laps=5), DRIVERS[:1], laps_df(5))
    assert rows(tmp_path, "SELECT COUNT(*), MAX(total_laps) FROM races") == [(1, 5)]
    assert rows(
        tmp_path, "SELECT race_id, code, COUNT(*) FROM drivers GROUP BY race_id, code HAVING COUNT(*) > 1"
    ) == []
    assert rows(tmp_path, "SELECT code FROM drivers") == [("VER",)]
    path = catalog.laps_path(tmp_path, RACE_ID)
    assert len(pd.read_parquet(path)) == 10
    assert sorted(p.name for p in path.parent.iterdir()) == ["laps.parquet"]


def test_catalog_failure_leaves_nothing(tmp_path, monkeypatch):
    bad = [DriverRecord("VER", None, None, "#3671C6", 1)]

    real_connect = catalog.connect

    def failing_connect(data_dir):
        conn = real_connect(data_dir)
        conn.execute("CREATE TRIGGER boom BEFORE INSERT ON drivers BEGIN SELECT RAISE(ABORT, 'boom'); END")
        return conn

    monkeypatch.setattr(storage.catalog, "connect", failing_connect)
    with pytest.raises(sqlite3.DatabaseError, match="boom"):
        store_race(tmp_path, race(), bad, laps_df())
    assert not catalog.race_dir(tmp_path, RACE_ID).exists()
    assert rows(tmp_path, "SELECT COUNT(*) FROM races") == [(0,)]


def test_failed_reingest_keeps_previous_data(tmp_path, monkeypatch):
    store_race(tmp_path, race(), DRIVERS, laps_df())
    real_connect = catalog.connect

    def failing_connect(data_dir):
        conn = real_connect(data_dir)
        conn.execute("CREATE TEMP TRIGGER boom BEFORE INSERT ON drivers BEGIN SELECT RAISE(ABORT, 'boom'); END")
        return conn

    monkeypatch.setattr(storage.catalog, "connect", failing_connect)
    with pytest.raises(sqlite3.DatabaseError):
        store_race(tmp_path, race(total_laps=5), DRIVERS, laps_df(5))
    path = catalog.laps_path(tmp_path, RACE_ID)
    assert len(pd.read_parquet(path)) == 6
    assert sorted(p.name for p in path.parent.iterdir()) == ["laps.parquet"]
    assert rows(tmp_path, "SELECT total_laps FROM races") == [(3,)]
    assert rows(tmp_path, "SELECT COUNT(*) FROM drivers") == [(2,)]


def test_file_swap_failure_rolls_back(tmp_path, monkeypatch):
    real_replace = storage.os.replace

    def failing_replace(src, dst):
        if str(src).endswith(".tmp"):
            raise OSError("disk full")
        return real_replace(src, dst)

    monkeypatch.setattr(storage.os, "replace", failing_replace)
    with pytest.raises(OSError):
        store_race(tmp_path, race(), DRIVERS, laps_df())
    assert not catalog.race_dir(tmp_path, RACE_ID).exists()
    assert rows(tmp_path, "SELECT COUNT(*) FROM races") == [(0,)]
    assert rows(tmp_path, "SELECT COUNT(*) FROM drivers") == [(0,)]


@pytest.mark.parametrize("bad_id", ["../evil", "2024-01-Bahrain", "2024-01-a/b", "x"])
def test_rejects_unsafe_race_id(tmp_path, bad_id):
    with pytest.raises(ValueError):
        store_race(tmp_path, race(race_id=bad_id), DRIVERS, laps_df())


def test_rejects_wrong_columns(tmp_path):
    with pytest.raises(ValueError):
        store_race(tmp_path, race(), DRIVERS, laps_df().drop(columns=["team"]))
