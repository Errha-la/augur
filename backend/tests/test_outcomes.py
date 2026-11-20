import sqlite3

import pytest
from synthetic import synthetic_race_laps

from augur import analyze, catalog
from augur.events.outcomes import degradation_outcome, resolve_outcomes, undercut_outcome, visible

# --- Undercut outcome (specs/event-outcomes "outcome table") -------------------


@pytest.mark.parametrize(
    "positions, total_laps, outcome, outcome_lap",
    [
        ({"NOR": 3, "PIA": 4}, 57, "hit", 26),
        ({"NOR": 4, "PIA": 3}, 57, "miss", 26),
        ({"NOR": 1, "PIA": 2}, 24, "void", 24),
    ],
)
def test_undercut_outcome_table(positions, total_laps, outcome, outcome_lap):
    asked = []

    def position_at(n):
        asked.append(n)
        return positions

    result = undercut_outcome(18, "NOR", "PIA", total_laps, position_at)
    assert (result["outcome"], result["outcome_lap"]) == (outcome, outcome_lap)
    assert "NOR" in result["outcome_text"] and "PIA" in result["outcome_text"]
    assert str(outcome_lap if outcome != "void" else 26) in result["outcome_text"]
    assert result["outcome_text"].endswith(".") and result["outcome_text"].count(". ") == 0
    # Void never looks at positions after the flag.
    assert asked == ([] if outcome == "void" else [26])


# --- Degradation outcome --------------------------------------------------------


def test_degradation_pit_on_lap_23():
    result = degradation_outcome(20, "HAM", 57, [12, 23], last_lap=57)
    assert result == {
        "outcome": "hit",
        "outcome_lap": 23,
        "outcome_text": "HAM pitted on lap 23, 3 laps after the warning.",
    }


def test_degradation_no_pit_inside_window():
    result = degradation_outcome(20, "HAM", 57, [31], last_lap=57)
    assert (result["outcome"], result["outcome_lap"]) == ("miss", 28)
    assert result["outcome_text"] == "HAM did not pit by lap 28, 8 laps after the warning."


def test_degradation_pit_on_the_last_window_lap_is_a_hit():
    assert degradation_outcome(20, "HAM", 57, [28], last_lap=57)["outcome"] == "hit"


def test_degradation_void_when_race_ends_first():
    result = degradation_outcome(20, "HAM", 24, [], last_lap=24)
    assert (result["outcome"], result["outcome_lap"]) == ("void", 24)


def test_degradation_hit_still_counts_near_the_end():
    # Race shorter than E+8 but the driver pitted inside it: decided by the pit.
    assert degradation_outcome(20, "HAM", 24, [22], last_lap=24)["outcome_lap"] == 22


def test_degradation_void_when_driver_stops_before_the_window_ends():
    result = degradation_outcome(20, "HAM", 57, [], last_lap=25)
    assert (result["outcome"], result["outcome_lap"]) == ("void", 57)


# --- resolve_outcomes on lap data -------------------------------------------------


def event(lap, type_, drivers, evidence=None):
    return {
        "id": f"x:{lap}:{type_}:{'-'.join(drivers)}", "lap": lap, "type": type_, "drivers": drivers,
        "severity": 60.0, "title": "t", "analysis": {"what": "w", "why": "y", "next": "n"},
        "evidence": evidence or {},
    }


def test_resolve_outcomes_uses_positions_and_pit_laps_from_laps():
    laps = synthetic_race_laps(seed=1, total_laps=30)  # AAA pits on 14, BBB 16, CCC 12
    drivers = [{"code": c, "team": "T", "team_color": "#000"} for c in laps["driver"].unique()]
    meta = {"race_id": "r", "total_laps": 30}
    events = [
        event(10, "degradation_warning", ["AAA"], {"driver": "AAA"}),  # pits on 14 → hit
        event(5, "degradation_warning", ["BBB"], {"driver": "BBB"}),  # pits on 16 > 13 → miss
        event(25, "degradation_warning", ["CCC"], {"driver": "CCC"}),  # 33 > 30 → void
        event(10, "undercut_window", ["FFF", "AAA"], {"chaser": "FFF", "ahead": "AAA"}),
        event(9, "pace_drop", ["DDD"]),
    ]
    out = resolve_outcomes(events, laps, drivers, meta)
    got = {e["id"]: (e["outcome"], e["outcome_lap"]) for e in out}
    assert got[events[0]["id"]] == ("hit", 14)
    assert got[events[1]["id"]] == ("miss", 13)
    assert got[events[2]["id"]] == ("void", 30)
    assert got[events[3]["id"]][0] in {"hit", "miss"} and got[events[3]["id"]][1] == 18
    assert got[events[4]["id"]] == (None, None)
    assert out[4]["outcome_text"] is None
    assert "outcome" not in events[0]  # inputs are not mutated


def test_visible_hides_until_outcome_lap():
    e = {"outcome": "hit", "outcome_lap": 23, "outcome_text": "x."}
    assert visible(e, 22) == {"outcome": None, "outcome_lap": None, "outcome_text": None}
    assert visible(e, 23)["outcome"] == "hit"
    assert visible({"outcome": None, "outcome_lap": None, "outcome_text": None}, 99)["outcome"] is None


# --- storage -----------------------------------------------------------------------


def test_analyze_stores_outcome_columns(fixture_race):
    e = {**event(1, "degradation_warning", ["AAA"]), "outcome": "void", "outcome_lap": 5, "outcome_text": "v."}
    analyze.replace_events(fixture_race.data_dir, fixture_race.race_id, "baseline", [e])
    conn = catalog.connect(fixture_race.data_dir)
    row = conn.execute("SELECT outcome, outcome_lap, outcome_text FROM events").fetchone()
    conn.close()
    assert tuple(row) == ("void", 5, "v.")


def test_connect_adds_outcome_columns_to_an_older_catalog(tmp_path):
    path = catalog.db_path(tmp_path)
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE events (race_id TEXT, model TEXT, id TEXT, lap INT, type TEXT, drivers TEXT,"
        " severity REAL, title TEXT, analysis TEXT, evidence TEXT, PRIMARY KEY (race_id, model, id))"
    )
    old.commit()
    old.close()
    conn = catalog.connect(tmp_path)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
    conn.close()
    assert {"outcome", "outcome_lap", "outcome_text"} <= cols
