import pytest
from fastapi.testclient import TestClient

from augur.api import create_app
from conftest import fixture_laps, write_race


@pytest.fixture
def client(fixture_race):
    return TestClient(create_app(fixture_race.data_dir))


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_races_ordered_by_year_then_round(tmp_path):
    data_dir = tmp_path / "data"
    laps = fixture_laps()
    write_race(data_dir, "2024-01-bahrain-grand-prix", laps, year=2024, round_=1,
               event_name="Bahrain Grand Prix", total_laps=5)
    write_race(data_dir, "2023-11-hungarian-grand-prix", laps, year=2023, round_=11,
               event_name="Hungarian Grand Prix", total_laps=5)
    r = TestClient(create_app(data_dir)).get("/api/races")
    assert r.status_code == 200
    body = r.json()
    assert [x["race_id"] for x in body] == [
        "2023-11-hungarian-grand-prix", "2024-01-bahrain-grand-prix",
    ]
    assert set(body[0]) == {"race_id", "year", "round", "event_name", "date", "total_laps"}


def test_races_empty_catalog(tmp_path):
    r = TestClient(create_app(tmp_path / "missing")).get("/api/races")
    assert r.status_code == 200 and r.json() == []
    from augur import catalog
    catalog.connect(tmp_path / "created").close()
    assert TestClient(create_app(tmp_path / "created")).get("/api/races").json() == []


def test_state(client, fixture_race):
    r = client.get(f"/api/races/{fixture_race.race_id}/state?lap=3")
    assert r.status_code == 200
    s = r.json()
    assert s["race_id"] == fixture_race.race_id and s["lap"] == 3 and s["total_laps"] == 5
    assert s["track_status"] == "2"
    assert [d["position"] for d in s["drivers"]] == [1, 2, 3]
    by = {d["code"]: d for d in s["drivers"]}
    assert by["BBB"]["stint"] == 2 and by["BBB"]["pit_count"] == 1
    assert by["BBB"]["compound"] == "HARD"
    assert by["AAA"]["team_color"] == "#3671C6"
    assert all(d["laps_completed"] == 3 for d in s["drivers"])


def test_state_null_lap_time(client, fixture_race):
    s = client.get(f"/api/races/{fixture_race.race_id}/state?lap=4").json()
    by = {d["code"]: d for d in s["drivers"]}
    assert by["CCC"]["last_lap_time_s"] is None


def test_laps_all_drivers(client, fixture_race):
    rows = client.get(f"/api/races/{fixture_race.race_id}/laps?lap=2").json()
    assert [(r["driver"], r["lap"]) for r in rows] == [
        (d, n) for d in ("AAA", "BBB", "CCC") for n in (1, 2)
    ]
    assert set(rows[0]) == {
        "driver", "team", "lap", "lap_time_s", "session_time_s", "stint", "compound",
        "tyre_life", "pit_in", "pit_out", "track_status", "is_accurate",
    }


def test_laps_filter_by_driver(client, fixture_race):
    rows = client.get(f"/api/races/{fixture_race.race_id}/laps?lap=4&driver=CCC").json()
    assert [r["driver"] for r in rows] == ["CCC"] * 4
    assert [r["lap"] for r in rows] == [1, 2, 3, 4]
    assert rows[3]["lap_time_s"] is None


def test_cors_only_allows_vite_origin(client):
    ok = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


@pytest.mark.parametrize(
    "path, status, detail",
    [
        ("/api/races/nope/state?lap=1", 404, "race not found"),
        ("/api/races/{id}/state?lap=0", 422, None),
        ("/api/races/{id}/state?lap={over}", 422, None),
        ("/api/races/{id}/state", 422, None),
        ("/api/races/{id}/laps?lap=2&driver=XXX", 404, "driver not found"),
        ("/api/races/nope/laps?lap=1", 404, "race not found"),
        ("/api/races/{id}/laps?lap={over}", 422, None),
        ("/api/races/{id}/laps", 422, None),
    ],
)
def test_errors(client, fixture_race, path, status, detail):
    url = path.format(id=fixture_race.race_id, over=fixture_race.total_laps + 1)
    r = client.get(url)
    assert r.status_code == status
    if detail is None:
        body = r.json()["detail"]
        assert isinstance(body, list) and body[0]["loc"] == ["query", "lap"]
    else:
        assert r.json() == {"detail": detail}
