"""/events serves cached commentary and commentary_model (llm-commentary 2.1)."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient
from synthetic import write_synthetic_race

from augur import analyze, catalog
from augur.api import create_app
from augur.narration.cache import CommentaryKey, store_text
from augur.narration.prompt import PROMPT_VERSION
from augur.narration.serving import serving_key

RACE = "2098-03-synthetic-grand-prix"


def fake_event(lap: int, driver: str) -> dict:
    return {
        "id": f"{RACE}:{lap}:pace_drop:{driver}", "lap": lap, "type": "pace_drop", "drivers": [driver],
        "severity": 50.0, "title": "t", "analysis": {"what": "w.", "why": "y.", "next": "n."},
        "evidence": {"driver": driver},
    }


@pytest.fixture
def data(tmp_path, monkeypatch):
    for var in ("AUGUR_NARRATOR", "GEMINI_MODEL", "AUGUR_LLM_MODEL", "AUGUR_COMMENTARY_LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AUGUR_MODEL", "baseline")
    d = tmp_path / "data"
    write_synthetic_race(d, 2098, 3, 3)
    analyze.replace_events(d, RACE, "baseline", [fake_event(5, "AAA"), fake_event(9, "BBB")])
    return d


def cache(data, event_id: str, text: str, **key) -> None:
    fields = {"model": "baseline", "narrator": "openai_compat", "llm_model": "glm", "lang": "en",
              "prompt_version": PROMPT_VERSION, **key}
    conn = catalog.connect(data)
    with conn:
        store_text(conn, event_id, CommentaryKey(**fields), text)
    conn.close()


def get_events(data, lap: int = 10) -> dict:
    return TestClient(create_app(data)).get(f"/api/races/{RACE}/events?lap={lap}").json()


def test_event_without_commentary(data):
    """Scenario: Event without commentary."""
    body = get_events(data)
    assert [e["commentary"] for e in body["events"]] == [None, None]
    assert body["commentary_model"] == "gemini-flash-latest"


def test_cached_text_for_current_settings(data, monkeypatch):
    monkeypatch.setenv("AUGUR_NARRATOR", "openai_compat")
    cache(data, f"{RACE}:5:pace_drop:AAA", "AAA lost time on lap 5.")
    body = get_events(data)
    assert body["commentary_model"] == "glm"
    assert {e["id"]: e["commentary"] for e in body["events"]} == {
        f"{RACE}:9:pace_drop:BBB": None,
        f"{RACE}:5:pace_drop:AAA": "AAA lost time on lap 5.",
    }


@pytest.mark.parametrize(
    "other",
    [{"llm_model": "nemotron"}, {"lang": "zh-TW"}, {"narrator": "gemini"}, {"model": "lightgbm"},
     {"prompt_version": PROMPT_VERSION + 1}],
)
def test_text_for_other_settings_is_not_served(data, monkeypatch, other):
    monkeypatch.setenv("AUGUR_NARRATOR", "openai_compat")
    cache(data, f"{RACE}:5:pace_drop:AAA", "stale", **other)
    assert all(e["commentary"] is None for e in get_events(data)["events"])


def test_none_narrator_and_invalid_settings(data, monkeypatch):
    cache(data, f"{RACE}:5:pace_drop:AAA", "x", narrator="none", llm_model="none")
    monkeypatch.setenv("AUGUR_NARRATOR", "none")
    body = get_events(data)
    assert body["commentary_model"] is None and all(e["commentary"] is None for e in body["events"])
    monkeypatch.setenv("AUGUR_NARRATOR", "nope")
    body = get_events(data)
    assert body["commentary_model"] is None and len(body["events"]) == 2
    monkeypatch.setenv("AUGUR_NARRATOR", "openai_compat")
    monkeypatch.setenv("AUGUR_LLM_MODEL", "bad model")
    assert get_events(data)["commentary_model"] is None


def test_serving_needs_no_key_or_server(monkeypatch):
    for var in ("GEMINI_API_KEY", "AUGUR_LLM_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AUGUR_NARRATOR", "openai_compat")
    assert serving_key("lightgbm") == CommentaryKey("lightgbm", "openai_compat", "glm", "en", PROMPT_VERSION)


def test_catalog_without_commentary_table(data):
    with sqlite3.connect(catalog.db_path(data)) as conn:
        conn.execute("DROP TABLE commentary")
    body = get_events(data)
    assert all(e["commentary"] is None for e in body["events"])
