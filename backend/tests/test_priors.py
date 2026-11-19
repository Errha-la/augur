import math

import pandas as pd
import pytest
from conftest import write_race

from augur.features import FEATURE_COLUMNS, build_feature_table
from augur.priors import circuit_priors
from augur.replay import ReplayStore
from augur.schema import LAP_COLUMNS

FUEL = 0.03 * 110 / 20


def stint_race(compound: str, slope: float, total=20) -> pd.DataFrame:
    """One driver, one stint, fuel-corrected time rising by ``slope`` per lap."""
    rows = []
    for lap in range(1, total + 1):
        rows.append(
            {
                "driver": "AAA", "team": "Red Team", "lap": lap,
                "lap_time_s": 90.0 + slope * lap - FUEL * (lap - 1),
                "session_time_s": 100.0 * lap, "stint": 1, "compound": compound,
                "tyre_life": lap, "pit_in": False, "pit_out": False,
                "track_status": "1", "is_accurate": lap > 1,
            }
        )
    return pd.DataFrame(rows, columns=list(LAP_COLUMNS))


@pytest.fixture
def season_store(tmp_path):
    data = tmp_path / "data"

    def add(race_id, year, rnd, location, laps):
        write_race(data, race_id, laps, year=year, round_=rnd, event_name=race_id,
                   total_laps=20, location=location)

    add("2023-01-bahrain-grand-prix", 2023, 1, "Sakhir", stint_race("MEDIUM", 0.07))
    add("2023-22-abu-dhabi-grand-prix", 2023, 22, "Yas Island", stint_race("HARD", 0.03))
    add("2024-01-bahrain-grand-prix", 2024, 1, "Sakhir", stint_race("MEDIUM", 0.1))
    add("2024-05-chinese-grand-prix", 2024, 5, "Shanghai", stint_race("MEDIUM", 0.1))
    add("2024-24-abu-dhabi-grand-prix", 2024, 24, "Yas Island", stint_race("HARD", 0.1))
    return data


def test_priors_by_season_table(season_store):
    store = ReplayStore(season_store)
    # 2024 Bahrain, MEDIUM <- 2023 Sakhir median MEDIUM slope
    assert circuit_priors(store, "2024-01-bahrain-grand-prix")["MEDIUM"] == pytest.approx(0.07, abs=1e-6)
    # 2024 Abu Dhabi, HARD <- 2023 Yas Island median HARD slope
    assert circuit_priors(store, "2024-24-abu-dhabi-grand-prix")["HARD"] == pytest.approx(0.03, abs=1e-6)
    # 2024 Shanghai: no 2023 race at the location -> null
    assert circuit_priors(store, "2024-05-chinese-grand-prix") == {}
    # A 2023 race has no earlier season ingested -> null
    assert circuit_priors(store, "2023-01-bahrain-grand-prix") == {}


def test_prior_null_when_previous_race_not_ingested(tmp_path):
    data = tmp_path / "data"
    write_race(data, "2024-24-abu-dhabi-grand-prix", stint_race("HARD", 0.1), year=2024, round_=24,
               event_name="x", total_laps=20, location="Yas Island")
    assert circuit_priors(ReplayStore(data), "2024-24-abu-dhabi-grand-prix") == {}


def test_prior_reaches_feature_table_by_compound(season_store):
    store = ReplayStore(season_store)
    laps = store.laps_until("2024-01-bahrain-grand-prix", 20)
    table = build_feature_table(laps, 20, circuit_priors(store, "2024-01-bahrain-grand-prix"))
    assert table["circuit_deg_prior_s"].dropna().round(6).unique().tolist() == [0.07]
    no_prior = build_feature_table(laps, 20, {})
    assert no_prior["circuit_deg_prior_s"].isna().all()


def test_two_teams_example():
    # Laps 15-19: team clean laps median 94.6 s, all clean laps median 95.0 s -> -0.4 at lap 20.
    rows = []
    times = {"T1": (94.6, 94.6), "T2": (95.4, 95.4)}  # field median = 95.0
    for lap in range(1, 21):
        for i, (team, ts) in enumerate(times.items()):
            for j, t in enumerate(ts):
                rows.append(
                    {
                        "driver": f"{team}{j}", "team": team, "lap": lap, "lap_time_s": t,
                        "session_time_s": 100.0 * lap, "stint": 1, "compound": "MEDIUM",
                        "tyre_life": lap, "pit_in": False, "pit_out": False,
                        "track_status": "1", "is_accurate": lap > 1,
                    }
                )
    table = build_feature_table(pd.DataFrame(rows, columns=list(LAP_COLUMNS)), 57)
    row = table[(table["team"] == "T1") & (table["target_lap"] == 20)].iloc[0]
    assert row["team_pace_gap_s"] == pytest.approx(-0.4)


def test_team_pace_gap_null_without_window_data():
    rows = [
        {"driver": "AAA", "team": "T", "lap": 1, "lap_time_s": 95.0, "session_time_s": 95.0,
         "stint": 1, "compound": "SOFT", "tyre_life": 1, "pit_in": False, "pit_out": False,
         "track_status": "1", "is_accurate": False}
    ]
    table = build_feature_table(pd.DataFrame(rows, columns=list(LAP_COLUMNS)), 57)
    assert math.isnan(table.iloc[0]["team_pace_gap_s"])


def test_no_driver_identity_feature():
    assert "driver" not in FEATURE_COLUMNS
    assert "team" not in FEATURE_COLUMNS
