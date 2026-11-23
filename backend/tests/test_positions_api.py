import pytest
from fastapi.testclient import TestClient

from augur import analyze
from augur.api import create_app

RACE = "2099-01-fixture-grand-prix"


def prediction(code: str, expected: float, p_win: float) -> dict:
    return {
        "code": code, "p_win": p_win, "p_podium": 1.0, "p_points": 1.0, "expected_position": expected,
        "position_p10": 1.0, "position_p90": 3.0,
    }


@pytest.fixture
def client(fixture_race, monkeypatch):
    monkeypatch.setenv("AUGUR_MODEL", "baseline")
    return TestClient(create_app(fixture_race.data_dir))


@pytest.fixture
def analyzed(fixture_race, client):
    # Stored deliberately out of expected-position order to check the API ordering.
    positions = {
        lap: [prediction("CCC", 2.9, 0.0), prediction("AAA", 1.1, 0.9), prediction("BBB", 2.0, 0.1)]
        for lap in range(1, fixture_race.total_laps + 1)
    }
    analyze.replace_positions(fixture_race.data_dir, RACE, "baseline", positions, runs=500, seed=7)
    return client


def test_positions_shape_and_order(analyzed):
    body = analyzed.get(f"/api/races/{RACE}/positions?lap=3").json()
    assert set(body) == {"race_id", "lap", "model", "analyzed", "runs", "seed", "drivers"}
    assert (body["race_id"], body["lap"], body["model"], body["analyzed"]) == (RACE, 3, "baseline", True)
    assert (body["runs"], body["seed"]) == (500, 7)
    assert [d["code"] for d in body["drivers"]] == ["AAA", "BBB", "CCC"]
    assert set(body["drivers"][0]) == {
        "code", "p_win", "p_podium", "p_points", "expected_position", "position_p10", "position_p90"
    }


def test_history_stops_at_the_current_lap(analyzed):
    body = analyzed.get(f"/api/races/{RACE}/positions/history?lap=4").json()
    assert set(body) == {"race_id", "model", "analyzed", "laps"}
    assert body["analyzed"] is True
    assert [entry["lap"] for entry in body["laps"]] == [1, 2, 3, 4]
    assert set(body["laps"][0]) == {"lap", "drivers"}
    assert set(body["laps"][0]["drivers"][0]) == {
        "code", "p_win", "p_podium", "expected_position", "position_p10", "position_p90"
    }
    assert [d["code"] for d in body["laps"][0]["drivers"]] == ["AAA", "BBB", "CCC"]


def test_race_not_analyzed(client):
    pos = client.get(f"/api/races/{RACE}/positions?lap=5")
    hist = client.get(f"/api/races/{RACE}/positions/history?lap=5")
    assert pos.status_code == hist.status_code == 200
    p, h = pos.json(), hist.json()
    assert p["analyzed"] is False and p["drivers"] == [] and p["runs"] is None and p["seed"] is None
    assert h["analyzed"] is False and h["laps"] == []


def test_other_model_is_not_served(analyzed, monkeypatch):
    monkeypatch.setenv("AUGUR_MODEL", "lightgbm")
    assert analyzed.get(f"/api/races/{RACE}/positions?lap=2").json()["analyzed"] is False


@pytest.mark.parametrize("path", ["positions", "positions/history"])
def test_errors(analyzed, path):
    assert analyzed.get(f"/api/races/2099-09-nope/{path}?lap=1").status_code == 404
    assert analyzed.get(f"/api/races/{RACE}/{path}?lap=0").status_code == 422
    assert analyzed.get(f"/api/races/{RACE}/{path}?lap=6").status_code == 422
    assert analyzed.get(f"/api/races/{RACE}/{path}").status_code == 422
