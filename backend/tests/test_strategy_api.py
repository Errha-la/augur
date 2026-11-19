import pytest
from fastapi.testclient import TestClient
from synthetic import write_synthetic_race

from augur.api import create_app

RACE = "2098-01-synthetic-grand-prix"


@pytest.fixture
def client(tmp_path):
    write_synthetic_race(tmp_path / "data", 2098, 1, 1)
    return TestClient(create_app(tmp_path / "data"))


def test_same_seed_twice(client):
    url = f"/api/races/{RACE}/strategy?lap=10&driver=DDD&seed=42"
    a, b = client.get(url), client.get(url)
    assert a.status_code == 200
    assert a.content == b.content
    body = a.json()
    assert set(body) == {"race_id", "lap", "driver", "runs", "seed", "pit_loss_s", "strategies"}
    assert body["runs"] == 1000 and body["seed"] == 42
    assert sum(s["win_probability"] for s in body["strategies"]) == pytest.approx(1.0, abs=0.001)
    assert [s["mean_s"] for s in body["strategies"]] == sorted(s["mean_s"] for s in body["strategies"])
    assert set(body["strategies"][0]) == {"name", "pit_lap", "mean_s", "p10_s", "p90_s", "win_probability"}


@pytest.mark.parametrize("runs", [50, 99, 5001])
def test_runs_out_of_range(client, runs):
    assert client.get(f"/api/races/{RACE}/strategy?lap=10&driver=DDD&runs={runs}").status_code == 422


def test_bounds_accepted(client):
    for runs in (100, 5000):
        assert client.get(f"/api/races/{RACE}/strategy?lap=10&driver=DDD&runs={runs}").status_code == 200


def test_unknown_race_driver_and_bad_seed(client):
    assert client.get("/api/races/nope/strategy?lap=10&driver=DDD").status_code == 404
    r = client.get(f"/api/races/{RACE}/strategy?lap=10&driver=XXX")
    assert r.status_code == 404 and r.json()["detail"] == "driver not found"
    assert client.get(f"/api/races/{RACE}/strategy?lap=10&driver=DDD&seed=-1").status_code == 422
    assert client.get(f"/api/races/{RACE}/strategy?lap=10").status_code == 422
