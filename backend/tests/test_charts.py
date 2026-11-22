import pandas as pd

from augur import charts
from augur.schema import LAP_COLUMNS

META = {"race_id": "r", "total_laps": 50}


def lap_row(driver, lap, lap_time, session, **kw):
    row = {
        "driver": driver, "team": "T", "lap": lap, "lap_time_s": lap_time, "session_time_s": session,
        "stint": 1, "compound": "MEDIUM", "tyre_life": lap, "pit_in": False, "pit_out": False,
        "track_status": "1", "is_accurate": True,
    }
    row.update(kw)
    return row


def frame(rows):
    return pd.DataFrame(rows, columns=list(LAP_COLUMNS)).astype({"tyre_life": "Int64"})


def catalog(*codes):
    return [{"code": c, "team": "T", "team_color": "#000000"} for c in codes]


# --- race trace ---------------------------------------------------------------


def test_faster_driver_gains():
    # Race start 1000.0 s; A race times 90/180/270, B 91/182/273.
    rows = [lap_row("A", n, 90.0, 1000.0 + 90.0 * n) for n in (1, 2, 3)]
    rows += [lap_row("B", n, 91.0, 1000.0 + 91.0 * n) for n in (1, 2, 3)]
    out = charts.race_trace(frame(rows), catalog("A", "B"), META, 3)
    assert out["reference_lap_s"] == 90.5
    by = {d["code"]: d["points"] for d in out["drivers"]}
    assert [p["delta_s"] for p in by["A"]] == [0.5, 1.0, 1.5]
    assert [p["delta_s"] for p in by["B"]] == [-0.5, -1.0, -1.5]
    assert [p["lap"] for p in by["A"]] == [1, 2, 3]
    assert [d["code"] for d in out["drivers"]] == ["A", "B"]  # running order
    assert set(out) == {"race_id", "lap", "reference_lap_s", "drivers"}
    assert set(out["drivers"][0]) == {"code", "team_color", "points"}


def test_trace_ignores_rows_after_lap_and_missing_session_times():
    rows = [lap_row("A", n, 90.0, 1000.0 + 90.0 * n) for n in (1, 2, 3)]
    rows[1]["session_time_s"] = None
    rows.append(lap_row("A", 4, 1.0, 1.0))
    out = charts.race_trace(frame(rows), catalog("A"), META, 3)
    assert [p["lap"] for p in out["drivers"][0]["points"]] == [1, 3]
    assert out["reference_lap_s"] == 90.0


def test_trace_without_lap_one_times():
    out = charts.race_trace(frame([lap_row("A", 1, None, None)]), catalog("A"), META, 1)
    assert out["reference_lap_s"] is None
    assert out["drivers"][0]["points"] == []


# --- rejoin -------------------------------------------------------------------


def gaps(**by_code):
    return [{"code": c, "gap_to_leader_s": g} for c, g in by_code.items()]


def test_rejoin_between_two_cars():
    slot = charts.rejoin_slot(gaps(A=0.0, B=5.0, C=20.0, D=24.0), "B", 21.5)
    assert slot == {
        "position": 4, "gap_to_leader_s": 26.5, "ahead": "D", "ahead_gap_s": 2.5,
        "behind": None, "behind_gap_s": None,
    }


def test_rejoin_leader_drops_behind_close_cars():
    slot = charts.rejoin_slot(gaps(A=0.0, B=5.0, C=30.0), "A", 21.5)
    assert slot["position"] == 2 and slot["gap_to_leader_s"] == 21.5
    assert (slot["ahead"], slot["ahead_gap_s"]) == ("B", 16.5)
    assert (slot["behind"], slot["behind_gap_s"]) == ("C", 8.5)


def test_rejoin_slot_null_without_gap():
    assert charts.rejoin_slot(gaps(A=0.0), "B", 21.5) is None


def test_rejoin_from_laps_uses_fallback_loss_and_leader_lap():
    rows = [lap_row("A", n, 90.0, 1000.0 + 90.0 * n) for n in (1, 2, 3)]
    rows += [lap_row("B", n, 92.0, 1000.0 + 92.0 * n) for n in (1, 2, 3)]
    out = charts.rejoin(frame(rows), catalog("A", "B"), META, 3, "A")
    assert out["pit_loss_s"] == 22.0  # no stop observed
    assert out["lap_length_s"] == 90.0  # leader's clean last lap
    assert out["cars"] == [
        {"code": "A", "position": 1, "gap_to_leader_s": 0.0, "laps_behind_leader": 0},
        {"code": "B", "position": 2, "gap_to_leader_s": 6.0, "laps_behind_leader": 0},
    ]
    assert out["rejoin"]["position"] == 2 and out["rejoin"]["ahead"] == "B"
    assert set(out) == {"race_id", "lap", "driver", "pit_loss_s", "lap_length_s", "cars", "rejoin"}


# --- stints and degradation -----------------------------------------------------


def one_stop(driver, pit_lap, total, base=90.0):
    rows = []
    for n in range(1, total + 1):
        stint = 1 if n <= pit_lap else 2
        rows.append(lap_row(
            driver, n, base, 1000.0 + base * n, stint=stint,
            compound="MEDIUM" if stint == 1 else "HARD",
            tyre_life=n if stint == 1 else n - pit_lap + 3,  # used set: age 4 on lap 1 of stint 2
            pit_in=n == pit_lap, pit_out=n == pit_lap + 1,
        ))
    return rows


def test_stint_still_running():
    out = charts.stints(frame(one_stop("A", 25, 40)), catalog("A", "B"), META, 30)
    assert set(out) == {"race_id", "lap", "drivers"}
    a = out["drivers"][0]
    assert a["code"] == "A"
    assert a["stints"] == [
        {"stint": 1, "compound": "MEDIUM", "start_lap": 1, "end_lap": 25, "start_tyre_age": 1},
        {"stint": 2, "compound": "HARD", "start_lap": 26, "end_lap": 30, "start_tyre_age": 4},
    ]
    assert out["drivers"][1] == {"code": "B", "stints": []}  # no laps yet


def test_degradation_too_few_points():
    # Stint 2 (HARD) starts lap 26 as an out-lap; laps 27-29 are the only clean HARD laps.
    out = charts.degradation_points(frame(one_stop("A", 25, 40)), 50, "r", 29)
    by = {c["compound"]: c for c in out["compounds"]}
    assert [c["compound"] for c in out["compounds"]] == ["MEDIUM", "HARD"]
    assert len(by["HARD"]["points"]) == 3 and by["HARD"]["fit"] is None
    assert set(by["HARD"]["points"][0]) == {"code", "lap", "tyre_age", "fuel_corrected_s"}


def test_degradation_fit_through_points():
    # Fuel-corrected time rises 0.1 s per lap of tyre age exactly.
    rows = [lap_row("A", n, 90.0 + 0.1 * n - charts.fuel_corrected(0.0, n, 50), 0.0) for n in range(1, 8)]
    out = charts.degradation_points(frame(rows), 50, "r", 7)
    (medium,) = out["compounds"]
    assert [p["lap"] for p in medium["points"]] == [2, 3, 4, 5, 6, 7]  # lap 1 is never clean
    assert medium["fit"] == {"slope_s_per_lap": 0.1, "intercept_s": 90.0, "n": 6}
