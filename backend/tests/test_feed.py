import ast
import inspect

import pytest

import augur.api
from augur.feed import RaceFeed, ReplayFeed
from augur.replay import RaceNotFound, ReplayStore


def test_replay_feed(fixture_race):
    feed = ReplayFeed(fixture_race.race_id, ReplayStore(fixture_race.data_dir))
    assert isinstance(feed, RaceFeed)
    assert feed.race_id == fixture_race.race_id
    assert feed.total_laps == 5
    assert feed.latest_lap() == 5
    laps = feed.laps_until(3)
    assert len(laps) == 9
    assert set(laps["lap"]) == {1, 2, 3}


def test_replay_feed_unknown_race(fixture_race):
    with pytest.raises(RaceNotFound):
        ReplayFeed("nope", ReplayStore(fixture_race.data_dir))


def test_api_reads_laps_only_through_a_feed():
    tree = ast.parse(inspect.getsource(augur.api))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute)]
    assert "pd" not in names and "pandas" not in names
    assert not any(a.attr in ("read_parquet", "laps_path") for a in attrs)
    # Every laps_until call goes through a variable named feed (a RaceFeed),
    # never through the ReplayStore.
    calls = [a for a in attrs if a.attr == "laps_until"]
    assert calls, "api must read laps via feed.laps_until"
    for a in calls:
        assert isinstance(a.value, ast.Name) and a.value.id == "feed"
