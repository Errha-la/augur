import sqlite3

import pytest
from fastapi.testclient import TestClient
from synthetic import write_synthetic_race

from augur import analyze, catalog
from augur.api import create_app

RACE = "2098-04-synthetic-grand-prix"


def stored_event(id_, lap, type_, outcome=None, outcome_lap=None):
    return {
        "id": id_, "lap": lap, "type": type_, "drivers": ["AAA"], "severity": 50.0, "title": "t",
        "analysis": {"what": "w.", "why": "y.", "next": "n."}, "evidence": {"driver": "AAA"},
        "outcome": outcome, "outcome_lap": outcome_lap,
        "outcome_text": None if outcome is None else "AAA pitted on lap 23, 3 laps after the warning.",
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_MODEL", "baseline")
    data = tmp_path / "data"
    write_synthetic_race(data, 2098, 4, 4, total_laps=45)
    analyze.replace_events(
        data,
        RACE,
        "baseline",
        [
            stored_event("deg", 20, "degradation_warning", "hit", 23),
            stored_event("pos", 21, "position_change"),
        ],
    )
    return TestClient(create_app(data))


def event_at(client, lap, id_):
    events = client.get(f"/api/races/{RACE}/events?lap={lap}").json()["events"]
    return next(e for e in events if e["id"] == id_)


# specs/event-outcomes "hit decided on lap 23"
@pytest.mark.parametrize("lap, outcome", [(22, None), (23, "hit"), (40, "hit")])
def test_outcome_revealed_only_from_the_deciding_lap(client, lap, outcome):
    e = event_at(client, lap, "deg")
    assert e["outcome"] == outcome
    if outcome is None:
        assert e["outcome_lap"] is None and e["outcome_text"] is None
    else:
        assert e["outcome_lap"] == 23
        assert e["outcome_text"] == "AAA pitted on lap 23, 3 laps after the warning."


def test_position_change_never_has_an_outcome(client):
    for lap in (21, 45):
        e = event_at(client, lap, "pos")
        assert (e["outcome"], e["outcome_lap"], e["outcome_text"]) == (None, None, None)


def test_events_from_a_catalog_without_outcome_columns(tmp_path, monkeypatch):
    # A catalog written before this change: the API must still answer, with null outcomes.
    monkeypatch.setenv("AUGUR_MODEL", "baseline")
    data = tmp_path / "data"
    write_synthetic_race(data, 2098, 4, 4, total_laps=45)
    conn = sqlite3.connect(catalog.db_path(data))
    conn.execute("DROP TABLE events")
    conn.execute(
        "CREATE TABLE events (race_id TEXT, model TEXT, id TEXT, lap INT, type TEXT, drivers TEXT,"
        " severity REAL, title TEXT, analysis TEXT, evidence TEXT)"
    )
    conn.execute(
        "INSERT INTO events VALUES (?, 'baseline', 'old', 5, 'degradation_warning', '[\"AAA\"]', 50,"
        " 't', '{\"what\": \"w\", \"why\": \"y\", \"next\": \"n\"}', '{}')",
        (RACE,),
    )
    conn.execute("INSERT INTO analyses VALUES (?, 'baseline', 1, '2026-01-01')", (RACE,))
    conn.commit()
    conn.close()
    e = event_at(TestClient(create_app(data)), 10, "old")
    assert e["outcome"] is None and e["outcome_lap"] is None
