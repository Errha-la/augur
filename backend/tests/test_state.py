import math

import pandas as pd

from augur.schema import LAP_COLUMNS
from augur.state import race_state

DRIVERS = [
    {"code": "A", "team": "TA", "team_color": "#111111"},
    {"code": "B", "team": "TB", "team_color": "#222222"},
    {"code": "C", "team": "TC", "team_color": "#333333"},
]
META = {"race_id": "r", "total_laps": 5}


def row(driver, lap, session, stint=1, lap_time=100.0, compound="SOFT", tyre=None, ts="1"):
    return {
        "driver": driver, "team": "T" + driver, "lap": lap, "lap_time_s": lap_time,
        "session_time_s": session, "stint": stint, "compound": compound,
        "tyre_life": lap if tyre is None else tyre, "pit_in": False, "pit_out": False,
        "track_status": ts, "is_accurate": True,
    }


def example_laps():
    rows = [
        row("A", 1, 100.0), row("A", 2, 200.0), row("A", 3, 300.0, ts="4"),
        row("B", 1, 101.0), row("B", 2, 201.0), row("B", 3, 302.5, stint=2, compound="HARD", tyre=1),
        row("C", 1, 105.0), row("C", 2, 210.0),
    ]
    return pd.DataFrame(rows, columns=list(LAP_COLUMNS))


def test_three_driver_example():
    s = race_state(example_laps(), DRIVERS, META, 3)
    d = {e["code"]: e for e in s["drivers"]}
    assert [e["code"] for e in s["drivers"]] == ["A", "B", "C"]
    assert [d[c]["position"] for c in "ABC"] == [1, 2, 3]
    assert d["B"]["gap_to_leader_s"] == 2.5
    assert d["B"]["pit_count"] == 1
    assert d["B"]["stint"] == 2 and d["B"]["compound"] == "HARD" and d["B"]["tyre_age_laps"] == 1
    assert d["C"]["laps_completed"] == 2
    assert d["C"]["laps_behind_leader"] == 1
    assert d["C"]["gap_to_leader_s"] == 10.0  # 210.0 - leader's lap-2 time 200.0
    assert d["A"]["gap_to_leader_s"] == 0.0 and d["A"]["laps_behind_leader"] == 0
    assert d["A"]["team_color"] == "#111111"
    assert s["track_status"] == "4"
    assert s["race_id"] == "r" and s["lap"] == 3 and s["total_laps"] == 5
    assert set(d["A"]) == {
        "code", "team", "team_color", "position", "laps_completed", "last_lap_time_s",
        "compound", "tyre_age_laps", "stint", "pit_count", "gap_to_leader_s",
        "laps_behind_leader",
    }


def test_missing_values_become_none():
    laps = example_laps()
    laps.loc[(laps["driver"] == "B") & (laps["lap"] == 3), ["lap_time_s", "compound"]] = [math.nan, None]
    d = {e["code"]: e for e in race_state(laps, DRIVERS, META, 3)["drivers"]}
    assert d["B"]["last_lap_time_s"] is None
    assert d["B"]["compound"] is None


def test_null_session_time_ranks_last_in_group_with_null_gap():
    laps = example_laps()
    laps.loc[(laps["driver"] == "A") & (laps["lap"] == 3), "session_time_s"] = math.nan
    s = race_state(laps, DRIVERS, META, 3)
    assert [e["code"] for e in s["drivers"]] == ["B", "A", "C"]
    d = {e["code"]: e for e in s["drivers"]}
    assert d["A"]["gap_to_leader_s"] is None
    assert d["B"]["gap_to_leader_s"] == 0.0


def test_rows_beyond_lap_are_ignored():
    laps = pd.concat(
        [example_laps(), pd.DataFrame([row("C", 3, 250.0), row("C", 4, 260.0)])],
        ignore_index=True,
    )
    s = race_state(laps, DRIVERS, META, 2)
    assert all(e["laps_completed"] == 2 for e in s["drivers"])
    assert [e["code"] for e in s["drivers"]] == ["A", "B", "C"]


def test_catalog_driver_without_laps_ranks_last():
    drivers = DRIVERS + [{"code": "D", "team": "TD", "team_color": "#444444"}]
    s = race_state(example_laps(), drivers, META, 3)
    last = s["drivers"][-1]
    assert last["code"] == "D" and last["position"] == 4
    assert last["laps_completed"] == 0 and last["laps_behind_leader"] == 3
    assert last["gap_to_leader_s"] is None and last["team"] == "TD"
