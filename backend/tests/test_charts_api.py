import pandas as pd
import pytest
from fastapi.testclient import TestClient
from synthetic import write_synthetic_race

from augur import catalog
from augur.api import create_app

RACE = "2098-01-synthetic-grand-prix"


@pytest.fixture
def data_dir(tmp_path):
    write_synthetic_race(tmp_path / "data", 2098, 1, 1)
    return tmp_path / "data"


@pytest.fixture
def client(data_dir):
    return TestClient(create_app(data_dir))


def scramble_after(data_dir, lap):
    """Rewrite every row after ``lap`` so any leak would change a response."""
    path = catalog.laps_path(data_dir, RACE)
    laps = pd.read_parquet(path)
    future = laps["lap"] > lap
    assert future.any()
    laps.loc[future, "lap_time_s"] = 1.0
    laps.loc[future, "session_time_s"] = 1.0
    laps.loc[future, "compound"] = "SOFT"
    laps.loc[future, "stint"] = 9
    laps.loc[future, "tyre_life"] = 99
    laps.loc[future, "pit_in"] = True
    laps.to_parquet(path, index=False)


def assert_no_future_laps(client, data_dir, url, lap):
    before = client.get(url)
    assert before.status_code == 200
    scramble_after(data_dir, lap)
    after = client.get(url)
    assert after.status_code == 200
    assert after.content == before.content


# --- trace --------------------------------------------------------------------


def test_trace_no_future_laps(client, data_dir):
    assert_no_future_laps(client, data_dir, f"/api/races/{RACE}/trace?lap=20", 20)


def test_trace_shape(client):
    body = client.get(f"/api/races/{RACE}/trace?lap=20").json()
    assert set(body) == {"race_id", "lap", "reference_lap_s", "drivers"}
    assert body["lap"] == 20 and len(body["drivers"]) == 6
    for d in body["drivers"]:
        assert set(d) == {"code", "team_color", "points"}
        assert [p["lap"] for p in d["points"]] == list(range(1, 21))


def test_trace_errors(client):
    r = client.get("/api/races/nope/trace?lap=5")
    assert r.status_code == 404 and r.json()["detail"] == "race not found"
    for lap in (0, 31):
        assert client.get(f"/api/races/{RACE}/trace?lap={lap}").status_code == 422


# --- rejoin -------------------------------------------------------------------


def test_rejoin_unknown_driver(client):
    r = client.get(f"/api/races/{RACE}/rejoin?lap=10&driver=XXX")
    assert r.status_code == 404 and r.json()["detail"] == "driver not found"
    assert client.get(f"/api/races/{RACE}/rejoin?lap=10").status_code == 422
    assert client.get("/api/races/nope/rejoin?lap=10&driver=AAA").status_code == 404


def test_rejoin_no_future_laps(client, data_dir):
    assert_no_future_laps(client, data_dir, f"/api/races/{RACE}/rejoin?lap=20&driver=DDD", 20)


def test_rejoin_shape(client):
    body = client.get(f"/api/races/{RACE}/rejoin?lap=20&driver=DDD").json()
    assert len(body["cars"]) == 6 and body["cars"][0]["gap_to_leader_s"] == 0.0
    assert body["pit_loss_s"] != 22.0  # stops observed by lap 20
    assert set(body["rejoin"]) == {
        "position", "gap_to_leader_s", "ahead", "ahead_gap_s", "behind", "behind_gap_s",
    }


# --- stints and degradation -----------------------------------------------------


def test_stints_no_future_laps(client, data_dir):
    assert_no_future_laps(client, data_dir, f"/api/races/{RACE}/stints?lap=20", 20)


def test_degradation_no_future_laps(client, data_dir):
    assert_no_future_laps(client, data_dir, f"/api/races/{RACE}/degradation?lap=20", 20)


def test_stints_and_degradation_shapes(client):
    st = client.get(f"/api/races/{RACE}/stints?lap=20").json()
    assert len(st["drivers"]) == 6 and all(len(d["stints"]) == 2 for d in st["drivers"])
    deg = client.get(f"/api/races/{RACE}/degradation?lap=20").json()
    assert set(deg) == {"race_id", "lap", "compounds"}
    assert [c["compound"] for c in deg["compounds"]] == ["MEDIUM", "HARD"]
    assert set(deg["compounds"][0]["fit"]) == {"slope_s_per_lap", "intercept_s", "n"}
    assert all(p["lap"] <= 20 for c in deg["compounds"] for p in c["points"])
    assert client.get("/api/races/nope/stints?lap=5").status_code == 404
    assert client.get(f"/api/races/{RACE}/degradation?lap=0").status_code == 422
