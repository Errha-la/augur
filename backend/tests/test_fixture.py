import sqlite3

import pandas as pd

from augur import catalog
from augur.schema import LAP_COLUMNS


def test_fixture_race_has_15_rows_and_one_catalog_race(fixture_race):
    laps = pd.read_parquet(catalog.laps_path(fixture_race.data_dir, fixture_race.race_id))
    assert len(laps) == 15
    assert tuple(laps.columns) == LAP_COLUMNS
    assert sorted(laps["driver"].unique()) == ["AAA", "BBB", "CCC"]
    assert laps["stint"].max() == 2
    assert laps["compound"].nunique() >= 2
    assert laps["track_status"].nunique() >= 2

    conn = sqlite3.connect(catalog.db_path(fixture_race.data_dir))
    try:
        races = conn.execute("SELECT race_id, total_laps FROM races").fetchall()
        colors = [r[0] for r in conn.execute("SELECT team_color FROM drivers")]
    finally:
        conn.close()
    assert races == [(fixture_race.race_id, 5)]
    assert len(colors) == 3
    assert all(c.startswith("#") and len(c) == 7 for c in colors)
