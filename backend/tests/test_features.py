import math

import pandas as pd
import pytest

from augur.features import (
    FEATURE_COLUMNS,
    build_feature_table,
    clean_mask,
    fuel_corrected,
    fuel_s_per_lap,
)
from augur.schema import LAP_COLUMNS


def lap_row(driver="HAM", lap=2, t=95.0, **kw):
    row = {
        "driver": driver,
        "team": kw.pop("team", "Silver"),
        "lap": lap,
        "lap_time_s": t,
        "session_time_s": 100.0 * lap,
        "stint": 1,
        "compound": "MEDIUM",
        "tyre_life": lap,
        "pit_in": False,
        "pit_out": False,
        "track_status": "1",
        "is_accurate": True,
    }
    row.update(kw)
    return row


def frame(rows):
    return pd.DataFrame(rows, columns=list(LAP_COLUMNS))


def test_fuel_correction_formula():
    assert fuel_s_per_lap(57) == pytest.approx(0.03 * 110 / 57)
    assert fuel_corrected(95.0, 11, 57) == pytest.approx(95.0 + 10 * 0.03 * 110 / 57)
    with pytest.raises(ValueError):
        fuel_s_per_lap(0)


def test_pit_lap_skipped_example():
    # Spec example "pit lap skipped": clean 2=95.0, 3=95.4, 4 pit-in 118.0, 5=95.2.
    rows = [
        lap_row(lap=1, t=99.0, is_accurate=False),
        lap_row(lap=2, t=95.0),
        lap_row(lap=3, t=95.4),
        lap_row(lap=4, t=118.0, pit_in=True, is_accurate=False),
        lap_row(lap=5, t=95.2),
    ]
    table = build_feature_table(frame(rows), total_laps=57)
    row = table[table["target_lap"] == 6].iloc[0]
    assert row["recent_pace_s"] == pytest.approx(95.2)
    assert row["recent_pace_trend_s"] == pytest.approx(0.0)
    assert row["laps_since_pit"] == 2  # 6 - 4
    assert row["lap_fraction"] == pytest.approx(6 / 57)


def test_non_green_and_lap_one_are_not_clean():
    rows = [
        lap_row(lap=1, t=95.0),
        lap_row(lap=2, t=95.0, track_status="4"),
        lap_row(lap=3, t=95.0, compound="INTERMEDIATE"),
        lap_row(lap=4, t=95.0, is_accurate=False),
        lap_row(lap=5, t=95.0),
    ]
    assert clean_mask(frame(rows)).tolist() == [False, False, False, False, True]


def test_lap_twelve_percent_slower_is_not_clean():
    rows = [
        lap_row("AAA", lap=2, t=90.0),
        lap_row("BBB", lap=3, t=90.0 * 1.12),  # 12% slower than fastest earlier clean lap
        lap_row("CCC", lap=3, t=90.0 * 1.09),  # 9% slower: still clean
    ]
    assert clean_mask(frame(rows)).tolist() == [True, False, True]


def test_outlier_reference_uses_only_earlier_laps():
    # A very fast lap 3 must not make lap 2 an outlier.
    rows = [lap_row("AAA", lap=2, t=100.0), lap_row("BBB", lap=3, t=80.0)]
    assert clean_mask(frame(rows)).tolist() == [True, True]


def test_altering_lap_k_does_not_change_lap_k_features():
    rows = [lap_row(lap=lap, t=95.0 + 0.1 * lap) for lap in range(1, 9)]
    rows += [lap_row("VER", lap=lap, t=94.0 + 0.1 * lap, team="Blue") for lap in range(1, 9)]
    before = build_feature_table(frame(rows), total_laps=57)
    altered = frame(rows)
    altered.loc[altered["lap"] == 6, ["lap_time_s", "compound", "stint", "tyre_life", "pit_in"]] = [
        150.0,
        "HARD",
        2,
        1,
        True,
    ]
    after = build_feature_table(altered, total_laps=57)
    cols = ["driver", "target_lap", *FEATURE_COLUMNS, "recent_pace_s"]
    b = before[before["target_lap"] <= 6][cols].reset_index(drop=True)
    a = after[after["target_lap"] <= 6][cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)
    # Sanity: lap 7's features do see the altered lap 6.
    assert not before[before["target_lap"] == 7]["compound"].equals(
        after[after["target_lap"] == 7]["compound"]
    )


def test_recent_pace_null_with_fewer_than_three_clean_laps():
    rows = [lap_row(lap=1), lap_row(lap=2), lap_row(lap=3)]
    table = build_feature_table(frame(rows), total_laps=57)
    row = table[table["target_lap"] == 4].iloc[0]
    assert math.isnan(row["recent_pace_s"])
    assert math.isnan(row["recent_pace_trend_s"])
