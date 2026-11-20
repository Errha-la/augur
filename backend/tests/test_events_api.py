import pandas as pd
import pytest
from fastapi.testclient import TestClient
from synthetic import synthetic_race_laps, write_synthetic_race

from augur import analyze, catalog, train
from augur.api import create_app
from augur.events.engine import EventEngine
from augur.feed import ReplayFeed
from augur.models.baseline import BaselineModel
from augur.replay import ReplayStore

RACE = "2098-03-synthetic-grand-prix"


def fake_event(lap: int, severity: float) -> dict:
    return {
        "id": f"{RACE}:{lap}:pace_drop:AAA", "lap": lap, "type": "pace_drop", "drivers": ["AAA"],
        "severity": severity, "title": "t", "analysis": {"what": "w.", "why": "y.", "next": "n."},
        "evidence": {"driver": "AAA"},
    }


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_MODEL", "baseline")
    d = tmp_path / "data"
    write_synthetic_race(d, 2098, 3, 3)
    return d


def test_events_filtered_by_lap(data):
    analyze.replace_events(data, RACE, "baseline", [fake_event(5, 30.0), fake_event(12, 50.0), fake_event(30, 90.0)])
    body = TestClient(create_app(data)).get(f"/api/races/{RACE}/events?lap=12").json()
    assert body["model"] == "baseline" and body["analyzed"] is True and body["lap"] == 12
    assert [e["lap"] for e in body["events"]] == [12, 5]
    assert set(body["events"][0]) == {"id", "lap", "type", "drivers", "severity", "title", "analysis", "evidence",
                                      "outcome", "outcome_lap", "outcome_text"}


def test_same_lap_ordered_by_severity(data):
    a = fake_event(7, 20.0)
    b = {**fake_event(7, 70.0), "id": f"{RACE}:7:pace_drop:BBB", "drivers": ["BBB"]}
    analyze.replace_events(data, RACE, "baseline", [a, b])
    body = TestClient(create_app(data)).get(f"/api/races/{RACE}/events?lap=7").json()
    assert [e["severity"] for e in body["events"]] == [70.0, 20.0]


def test_not_analyzed(data):
    body = TestClient(create_app(data)).get(f"/api/races/{RACE}/events?lap=10").json()
    assert body["analyzed"] is False and body["events"] == []


def test_analyzed_with_zero_events_and_other_model(data, monkeypatch):
    analyze.replace_events(data, RACE, "baseline", [])
    assert TestClient(create_app(data)).get(f"/api/races/{RACE}/events?lap=10").json()["analyzed"] is True
    monkeypatch.setenv("AUGUR_MODEL", "lightgbm")
    body = TestClient(create_app(data)).get(f"/api/races/{RACE}/events?lap=10").json()
    assert body["model"] == "lightgbm" and body["analyzed"] is False


def test_events_validation(data):
    client = TestClient(create_app(data))
    assert client.get("/api/races/nope/events?lap=1").status_code == 404
    assert client.get(f"/api/races/{RACE}/events?lap=0").status_code == 422
    assert client.get(f"/api/races/{RACE}/events?lap=31").status_code == 422


def test_end_to_end_analyze_then_serve(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_MODEL", "baseline")
    d = tmp_path / "data"
    for rnd, seed in ((1, 1), (2, 2), (3, 3)):
        write_synthetic_race(d, 2098, rnd, seed)
    train.train("baseline", [(2098, 1), (2098, 2)], [(2098, 3)], d)
    assert analyze.main(["--race", RACE, "--model", "baseline", "--data-dir", str(d)]) == 0
    body = TestClient(create_app(d)).get(f"/api/races/{RACE}/events?lap=30").json()
    assert body["events"] and all(e["lap"] <= 30 for e in body["events"])


def test_events_unaffected_by_future_laps(tmp_path):
    n = 18
    d = tmp_path / "data"
    write_synthetic_race(d, 2098, 3, 3)

    def run():
        feed = ReplayFeed(RACE, ReplayStore(d))
        engine = EventEngine(feed, BaselineModel())
        return [e for lap in range(1, n + 1) for e in engine.step(lap)]

    before = run()
    assert before
    path = catalog.laps_path(d, RACE)
    laps = pd.read_parquet(path)
    future = laps["lap"] > n
    laps.loc[future, "lap_time_s"] = 60.0
    laps.loc[future, "session_time_s"] = 1.0
    laps.loc[future, "compound"] = "SOFT"
    laps.loc[future, "pit_in"] = True
    laps.loc[future, "stint"] = 9
    laps.to_parquet(path, index=False)
    assert not pd.read_parquet(path).equals(synthetic_race_laps(3))
    assert run() == before
