import math

import numpy as np
import pandas as pd
import pytest

from augur.ingest import SOURCE_COLUMNS, make_race_id, normalize_laps, slugify, team_color
from augur.schema import DEFAULT_TEAM_COLOR, LAP_COLUMNS


def fastf1_row(**overrides):
    row = {
        "Driver": "VER",
        "Team": "Red Bull Racing",
        "LapNumber": 3.0,
        "LapTime": pd.Timedelta("0:01:36.512"),
        "Time": pd.Timedelta("0:58:01.250"),
        "Stint": 1.0,
        "Compound": "SOFT",
        "TyreLife": 3.0,
        "PitInTime": pd.NaT,
        "PitOutTime": pd.Timedelta("0:52:10"),
        "TrackStatus": "1",
        "IsAccurate": True,
        "Sector1Time": pd.Timedelta("0:00:30"),  # extra FastF1 column is ignored
    }
    row.update(overrides)
    return row


def frame(*rows):
    rows = list(rows)
    df = pd.DataFrame(rows)
    for col in ("LapTime", "Time", "PitInTime", "PitOutTime"):
        df[col] = pd.Series([r[col] for r in rows], dtype="timedelta64[ns]")
    return df


def test_one_lap_row_example():
    out = normalize_laps(frame(fastf1_row()))
    assert tuple(out.columns) == LAP_COLUMNS
    row = out.iloc[0]
    assert row["driver"] == "VER"
    assert row["lap"] == 3
    assert row["lap_time_s"] == pytest.approx(96.512)
    assert row["session_time_s"] == pytest.approx(3481.25)
    assert row["pit_in"] is np.False_ or row["pit_in"] == False  # noqa: E712
    assert bool(row["pit_out"]) is True
    assert row["stint"] == 1 and row["tyre_life"] == 3
    assert row["compound"] == "SOFT" and row["track_status"] == "1"
    assert bool(row["is_accurate"]) is True


def test_dtypes():
    out = normalize_laps(frame(fastf1_row()))
    assert out["lap"].dtype == "int64"
    assert out["lap_time_s"].dtype == "float64"
    assert out["session_time_s"].dtype == "float64"
    assert str(out["stint"].dtype) == "Int64"
    assert str(out["tyre_life"].dtype) == "Int64"
    for col in ("pit_in", "pit_out", "is_accurate"):
        assert out[col].dtype == "bool"


def test_missing_lap_time_is_null_not_zero():
    out = normalize_laps(
        frame(
            fastf1_row(
                LapTime=pd.NaT,
                Time=pd.NaT,
                Compound=np.nan,
                TyreLife=np.nan,
                Stint=np.nan,
                IsAccurate=np.nan,
            )
        )
    )
    row = out.iloc[0]
    assert math.isnan(row["lap_time_s"])
    assert math.isnan(row["session_time_s"])
    assert row["compound"] is None
    assert pd.isna(row["tyre_life"]) and pd.isna(row["stint"])
    assert bool(row["is_accurate"]) is False


def test_missing_column_raises_keyerror_naming_it():
    df = frame(fastf1_row()).drop(columns=["LapTime", "PitOutTime"])
    with pytest.raises(KeyError, match="LapTime.*PitOutTime"):
        normalize_laps(df)


def test_source_columns_cover_schema():
    assert len(SOURCE_COLUMNS) == len(LAP_COLUMNS) == 12


def test_non_integer_lap_number_rejected():
    with pytest.raises(ValueError):
        normalize_laps(frame(fastf1_row(LapNumber=3.5)))


@pytest.mark.parametrize(
    ("year", "rnd", "name", "expected"),
    [
        (2024, 1, "Bahrain Grand Prix", "2024-01-bahrain-grand-prix"),
        (2023, 11, "Hungarian Grand Prix", "2023-11-hungarian-grand-prix"),
        (2024, 24, "Abu Dhabi Grand Prix", "2024-24-abu-dhabi-grand-prix"),
    ],
)
def test_race_id(year, rnd, name, expected):
    assert make_race_id(year, rnd, name) == expected


def test_slug_is_path_safe():
    assert slugify("  São Paulo / ../Grand Prix!! ") == "s-o-paulo-grand-prix"
    with pytest.raises(ValueError):
        slugify("../")


@pytest.mark.parametrize("bad", [(0, "X"), (100, "X"), (-1, "X")])
def test_race_id_rejects_bad_round(bad):
    with pytest.raises(ValueError):
        make_race_id(2024, *bad)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("3671C6", "#3671C6"), ("#e8002d", "#E8002D"), ("", DEFAULT_TEAM_COLOR),
     (np.nan, DEFAULT_TEAM_COLOR), (None, DEFAULT_TEAM_COLOR), ("zzzzzz", DEFAULT_TEAM_COLOR)],
)
def test_team_color(value, expected):
    assert team_color(value) == expected
