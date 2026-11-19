import pandas as pd
import pytest
from fastapi.testclient import TestClient
from synthetic import write_synthetic_race

from augur import catalog, train
from augur.api import create_app

RACE = "2098-03-synthetic-grand-prix"


@pytest.fixture(scope="module")
def trained_data(tmp_path_factory):
    data = tmp_path_factory.mktemp("pred") / "data"
    for rnd, seed in ((1, 1), (2, 2), (3, 3)):
        write_synthetic_race(data, 2098, rnd, seed)
    for name in ("baseline", "lightgbm"):
        train.train(name, [(2098, 1), (2098, 2)], [(2098, 3)], data)
    return data


@pytest.fixture
def client(trained_data, monkeypatch):
    monkeypatch.delenv("AUGUR_MODEL", raising=False)
    return TestClient(create_app(trained_data))


def test_not_enough_clean_laps(client):
    r = client.get(f"/api/races/{RACE}/predictions?lap=2")
    assert r.status_code == 200
    body = r.json()
    assert body["race_id"] == RACE and body["lap"] == 2
    assert len(body["drivers"]) == 6
    assert all(d["predicted_next_lap_s"] is None for d in body["drivers"])


def test_lightgbm_predictions_fields(client):
    body = client.get(f"/api/races/{RACE}/predictions?lap=10").json()
    d = body["drivers"][0]
    assert set(d) == {"code", "predicted_next_lap_s", "recent_pace_s", "deg_s_per_lap", "deg_laps", "cliff"}
    assert all(x["predicted_next_lap_s"] is not None for x in body["drivers"])
    assert all(x["deg_s_per_lap"] is not None for x in body["drivers"])


def test_baseline_predicts_recent_pace(trained_data, monkeypatch):
    monkeypatch.setenv("AUGUR_MODEL", "baseline")
    body = TestClient(create_app(trained_data)).get(f"/api/races/{RACE}/predictions?lap=10").json()
    for d in body["drivers"]:
        assert d["predicted_next_lap_s"] == d["recent_pace_s"]


def test_unknown_and_untrained_model(trained_data, monkeypatch, tmp_path):
    monkeypatch.setenv("AUGUR_MODEL", "nope")
    r = TestClient(create_app(trained_data)).get(f"/api/races/{RACE}/predictions?lap=10")
    assert r.status_code == 503 and r.json()["detail"] == "unknown model nope"

    monkeypatch.setenv("AUGUR_MODEL", "lightgbm")
    empty = tmp_path / "empty"
    write_synthetic_race(empty, 2098, 3, 3)
    r = TestClient(create_app(empty)).get(f"/api/races/{RACE}/predictions?lap=10")
    assert r.status_code == 503
    assert r.json()["detail"] == "model lightgbm is not trained, run augur.train first"


def test_invalid_requests(client):
    assert client.get("/api/races/nope/predictions?lap=1").status_code == 404
    assert client.get(f"/api/races/{RACE}/predictions?lap=0").status_code == 422
    assert client.get(f"/api/races/{RACE}/predictions?lap=31").status_code == 422
    assert client.get(f"/api/races/{RACE}/predictions").status_code == 422


def test_predictions_unaffected_by_future_laps(tmp_path, trained_data, monkeypatch):
    monkeypatch.delenv("AUGUR_MODEL", raising=False)
    data = tmp_path / "data"
    write_synthetic_race(data, 2098, 3, 3)
    (data / "models").mkdir()
    for f in (trained_data / "models").iterdir():
        (data / "models" / f.name).write_bytes(f.read_bytes())
    client = TestClient(create_app(data))
    url = f"/api/races/{RACE}/predictions?lap=12"
    before = client.get(url)
    assert before.status_code == 200

    path = catalog.laps_path(data, RACE)
    laps = pd.read_parquet(path)
    future = laps["lap"] > 12
    laps.loc[future, "lap_time_s"] = 60.0
    laps.loc[future, "compound"] = "SOFT"
    laps.loc[future, "pit_in"] = True
    laps.loc[future, "stint"] = 7
    laps.loc[future, "track_status"] = "4"
    laps.to_parquet(path, index=False)
    assert client.get(f"/api/races/{RACE}/predictions?lap=14").content != client.get(
        f"/api/races/{RACE}/predictions?lap=12"
    ).content

    after = client.get(url)
    assert after.content == before.content
