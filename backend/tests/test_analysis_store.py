"""Re-analysis writes: one transaction, and commentary dropped only for changed events."""

from __future__ import annotations

import pytest
from synthetic import write_synthetic_race

from augur import analyze, catalog
from augur.narration.cache import CommentaryKey, cached_texts, store_text
from augur.replay import ReplayStore

RACE = "2098-03-synthetic-grand-prix"
KEY = CommentaryKey("baseline", "openai_compat", "glm", "en", 1)


def event(lap: int, driver: str, deg: float) -> dict:
    return {
        "id": f"{RACE}:{lap}:degradation_warning:{driver}", "lap": lap, "type": "degradation_warning",
        "drivers": [driver], "severity": 50.0, "title": "t",
        "analysis": {"what": f"{driver} loses {deg} s/lap.", "why": "y.", "next": "n."},
        "evidence": {"driver": driver, "deg_s_per_lap": deg},
    }


def position(code: str) -> dict:
    return {"code": code, "p_win": 0.5, "p_podium": 0.9, "p_points": 1.0, "expected_position": 1.5,
            "position_p10": 1.0, "position_p90": 2.0, "position_distribution": [0.5, 0.5]}


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "data"
    write_synthetic_race(d, 2098, 3, 3)
    analyze.store_analysis(d, RACE, "baseline", [event(5, "AAA", 0.12), event(9, "BBB", 0.2)],
                           {1: [position("AAA")]}, runs=100, seed=42)
    conn = catalog.connect(d)
    with conn:
        for e in (event(5, "AAA", 0.12), event(9, "BBB", 0.2)):
            store_text(conn, e["id"], KEY, f"{e['drivers'][0]} commentary")
    conn.close()
    return d


def texts(data) -> dict[str, str]:
    conn = catalog.connect(data)
    try:
        return cached_texts(conn, [event(5, "AAA", 0)["id"], event(9, "BBB", 0)["id"]], KEY)
    finally:
        conn.close()


def test_reanalysis_drops_commentary_only_for_changed_events(data):
    # AAA's evidence changed (0.12 -> 0.14); BBB's event is identical.
    analyze.store_analysis(data, RACE, "baseline", [event(5, "AAA", 0.14), event(9, "BBB", 0.2)],
                           {1: [position("AAA")]}, runs=100, seed=42)
    assert texts(data) == {event(9, "BBB", 0)["id"]: "BBB commentary"}


def test_reanalysis_drops_commentary_of_removed_events(data):
    analyze.store_analysis(data, RACE, "baseline", [event(9, "BBB", 0.2)], {1: [position("AAA")]},
                           runs=100, seed=42)
    assert texts(data) == {event(9, "BBB", 0)["id"]: "BBB commentary"}


def test_failed_position_write_keeps_the_previous_analysis(data):
    store = ReplayStore(data)
    before = (store.analyzed_at(RACE, "baseline"), store.events_until(RACE, "baseline", 99))
    bad = {1: [{"code": "AAA"}]}  # missing fields: the positions insert fails
    with pytest.raises(KeyError):
        analyze.store_analysis(data, RACE, "baseline", [event(5, "AAA", 0.3)], bad, runs=100, seed=42)
    assert (store.analyzed_at(RACE, "baseline"), store.events_until(RACE, "baseline", 99)) == before
    assert len(texts(data)) == 2
