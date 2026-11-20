import json
import shutil

import pytest
from fastapi.testclient import TestClient
from synthetic import write_synthetic_race

from augur import analyze, bench, train
from augur.api import create_app
from augur.wrapped import pick_highlights, podium_call

RACE = "2098-06-synthetic-grand-prix"  # 58 laps, analyzed
UNANALYZED = "2098-07-synthetic-grand-prix"


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    d = tmp_path_factory.mktemp("wrapped") / "data"
    for rnd, seed in ((1, 1), (2, 2), (3, 3)):
        write_synthetic_race(d, 2098, rnd, seed)
    write_synthetic_race(d, 2098, 6, 6, total_laps=58)
    write_synthetic_race(d, 2098, 7, 7, total_laps=58)
    train.train("baseline", [(2098, 1), (2098, 2)], [(2098, 3)], d)
    assert analyze.main(["--race", RACE, "--model", "baseline", "--runs", "100", "--data-dir", str(d)]) == 0
    return d


@pytest.fixture
def data(prepared, tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_MODEL", "baseline")
    d = tmp_path / "data"
    shutil.copytree(prepared, d)
    return d


@pytest.fixture
def client(data):
    return TestClient(create_app(data))


# --- Wrapped unlocks at the final lap (task 3.1) ---------------------------------------


# Example: 58-lap race (AAA stands in for VER)
@pytest.mark.parametrize(
    "query, status, detail",
    [
        ("lap=57&driver=AAA", 409, "wrapped unlocks at the final lap"),
        ("lap=58&driver=AAA", 200, None),
        ("lap=58&driver=XXX", 404, "driver not found"),
    ],
)
def test_58_lap_race(client, query, status, detail):
    r = client.get(f"/api/races/{RACE}/wrapped?{query}")
    assert r.status_code == status
    if detail:
        assert r.json() == {"detail": detail}


def test_not_analyzed_race(client):
    r = client.get(f"/api/races/{UNANALYZED}/wrapped?lap=58&driver=AAA")
    assert (r.status_code, r.json()) == (409, {"detail": "race not analyzed"})


def test_unknown_race(client):
    assert client.get("/api/races/2098-99-nope/wrapped?lap=58&driver=AAA").status_code == 404


# --- Wrapped content (task 3.2) ----------------------------------------------------------


def ev(id_, lap, type_, severity, outcome=None):
    return {"id": id_, "lap": lap, "type": type_, "drivers": ["AAA"], "severity": severity, "outcome": outcome}


# Example: four events
def test_picking_the_highlights():
    events = [
        ev("a", 10, "degradation_warning", 70, "hit"),
        ev("b", 18, "undercut_window", 60, "hit"),
        ev("c", 30, "undercut_window", 60, "miss"),
        ev("d", 44, "position_change", 90),
    ]
    h = pick_highlights(events)
    assert (h["best_call"]["id"], h["biggest_miss"]["id"], h["biggest_moment"]["id"]) == ("a", "c", "d")


def test_highlight_ties_break_by_earliest_lap_and_none_is_null():
    h = pick_highlights([ev("late", 30, "undercut_window", 60, "hit"), ev("early", 12, "undercut_window", 60, "hit")])
    assert h["best_call"]["id"] == "early"
    assert h["biggest_miss"] is None
    assert pick_highlights([]) == {"best_call": None, "biggest_miss": None, "biggest_moment": None}


# Example: two of three
def test_podium_call_two_of_three():
    call = podium_call(29, {"VER": 0.92, "NOR": 0.71, "LEC": 0.55, "PIA": 0.40, "HAM": 0.2}, ["VER", "LEC", "PIA"])
    assert call["lap"] == 29
    assert [p["code"] for p in call["predicted"]] == ["VER", "NOR", "LEC"]
    assert [p["p_podium"] for p in call["predicted"]] == [0.92, 0.71, 0.55]
    assert (call["actual"], call["correct"]) == (["VER", "LEC", "PIA"], 2)


def test_wrapped_content_shape(client):
    body = client.get(f"/api/races/{RACE}/wrapped?lap=58&driver=AAA").json()
    assert set(body) == {
        "race_id", "event_name", "year", "model", "summary", "podium_call", "score", "hit_rate",
        "best_call", "biggest_miss", "biggest_moment", "driver",
    }
    assert (body["race_id"], body["event_name"], body["year"]) == (RACE, "Synthetic Grand Prix", 2098)
    assert body["model"]["name"] == "baseline" and body["model"]["author"]
    summary = body["summary"]
    assert summary["total_laps"] == 58 and len(summary["podium"]) == 3 and summary["winner"] == summary["podium"][0]
    assert summary["n_events"] == sum(summary["n_events_by_type"].values())
    assert body["podium_call"]["lap"] == 29 and len(body["podium_call"]["predicted"]) == 3
    assert set(body["score"]) == {
        "position_skill_pct", "brier_model", "brier_baseline", "lap_improvement_pct", "mae_model_s", "mae_baseline_s",
    }
    d = body["driver"]
    assert (d["code"], d["team"]) == ("AAA", "Red Team")
    assert [p["lap"] for p in d["positions_by_lap"]] == list(range(1, 59))
    assert len(d["p_podium_by_lap"]) == 58
    assert d["final_position"] == d["positions_by_lap"][-1]["position"]
    assert sum(s["laps"] for s in d["stints"]) == 58 and [s["compound"] for s in d["stints"]] == ["MEDIUM", "HARD"]
    assert all("AAA" in e["drivers"] for e in d["events"])
    assert [e["lap"] for e in d["events"]] == sorted(e["lap"] for e in d["events"])
    # At the final lap every resolved outcome is visible.
    assert all(e["outcome"] is not None for e in d["events"] if e["type"] in ("undercut_window", "degradation_warning"))


# Scenario: Score matches the bench
def test_score_matches_the_bench(data, client, tmp_path):
    out = tmp_path / "bench"
    argv = ["--model", "baseline", "--data-dir", str(data), "--out-dir", str(out), "--runs", "100"]
    assert bench.main(argv, races=(RACE,)) == 0
    per_race = json.loads((out / "baseline.json").read_text())["per_race"][0]
    score = client.get(f"/api/races/{RACE}/wrapped?lap=58&driver=AAA").json()["score"]
    assert per_race["race_id"] == RACE
    for key in ("position_skill_pct", "lap_improvement_pct", "brier_model", "mae_model_s"):
        assert score[key] == per_race[key]
