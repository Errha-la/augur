import pytest

from augur.replay import RaceNotFound, ReplayStore
from augur.schema import LAP_COLUMNS


def test_laps_until_returns_only_laps_up_to_cutoff(fixture_race):
    store = ReplayStore(fixture_race.data_dir)
    laps = store.laps_until(fixture_race.race_id, 3)
    assert len(laps) == 9
    assert sorted(laps["lap"].unique()) == [1, 2, 3]
    assert tuple(laps.columns) == LAP_COLUMNS


def test_laps_until_returns_a_copy(fixture_race):
    store = ReplayStore(fixture_race.data_dir)
    first = store.laps_until(fixture_race.race_id, 2)
    first.loc[:, "lap_time_s"] = -1.0
    assert (store.laps_until(fixture_race.race_id, 2)["lap_time_s"] > 0).all()


def test_catalog_lookups(fixture_race):
    store = ReplayStore(fixture_race.data_dir)
    races = store.list_races()
    assert [r["race_id"] for r in races] == [fixture_race.race_id]
    assert store.get_race(fixture_race.race_id)["total_laps"] == 5
    assert store.get_race("nope") is None
    assert [d["code"] for d in store.list_drivers(fixture_race.race_id)] == ["AAA", "BBB", "CCC"]
    assert store.list_drivers("nope") == []


def test_unknown_or_traversal_race_id_never_touches_filesystem(fixture_race):
    store = ReplayStore(fixture_race.data_dir)
    for bad in ("nope", "../races/" + fixture_race.race_id, "..", ""):
        with pytest.raises(RaceNotFound):
            store.laps_until(bad, 1)


def test_laps_until_rejects_non_int_lap(fixture_race):
    store = ReplayStore(fixture_race.data_dir)
    with pytest.raises(TypeError):
        store.laps_until(fixture_race.race_id, "3")


def test_missing_catalog_lists_nothing_and_creates_no_file(tmp_path):
    store = ReplayStore(tmp_path / "empty")
    assert store.list_races() == []
    assert store.get_race("x") is None
    assert not (tmp_path / "empty").exists()
