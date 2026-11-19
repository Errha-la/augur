import pandas as pd
import pytest
from synthetic import synthetic_race_laps

from augur import config
from augur.schema import LAP_COLUMNS
from augur.strategy import NO_STOP, candidate_strategies, pit_loss, simulate


def one_driver(total=57, upto=15, compounds=None):
    compounds = compounds or {}
    rows = []
    for lap in range(1, upto + 1):
        rows.append(
            {"driver": "DDD", "team": "T", "lap": lap, "lap_time_s": 95.0 + 0.05 * lap,
             "session_time_s": 95.0 * lap, "stint": 1, "compound": compounds.get(lap, "MEDIUM"),
             "tyre_life": lap, "pit_in": False, "pit_out": False, "track_status": "1",
             "is_accurate": lap > 1}
        )
    return pd.DataFrame(rows, columns=list(LAP_COLUMNS))


def test_driver_who_has_not_used_two_compounds():
    names = [n for n, _ in candidate_strategies(one_driver(), 57, "DDD", 15)]
    assert names == ["pit on lap 16", "pit on lap 18", "pit on lap 20", "pit on lap 23"]


def test_no_further_stop_after_two_dry_compounds():
    laps = one_driver(compounds={lap: "HARD" for lap in range(10, 16)})
    names = [n for n, _ in candidate_strategies(laps, 57, "DDD", 15)]
    assert names[0] == NO_STOP


def test_wet_compound_does_not_count_as_second_dry():
    laps = one_driver(compounds={2: "INTERMEDIATE"})
    assert NO_STOP not in [n for n, _ in candidate_strategies(laps, 57, "DDD", 15)]


def test_late_in_the_race():
    pits = [n for n, p in candidate_strategies(one_driver(upto=53), 57, "DDD", 53) if p is not None]
    assert pits == ["pit on lap 54"]


def test_pit_loss_fallback_without_stops():
    assert pit_loss(one_driver()) is None
    assert simulate(one_driver(), 57, "DDD", 15)["pit_loss_s"] == config.PIT_LOSS_FALLBACK_S


def test_pit_loss_observed_from_synthetic_stops():
    # Synthetic stops add 10 s (in-lap) + 12 s (out-lap) on top of pace.
    loss = pit_loss(synthetic_race_laps(1))
    assert 20.0 < loss < 24.0


def test_simulation_is_reproducible_and_ordered():
    laps = synthetic_race_laps(1)
    a = simulate(laps, 30, "DDD", 10, runs=500, seed=7)
    b = simulate(laps, 30, "DDD", 10, runs=500, seed=7)
    assert a == b
    means = [s["mean_s"] for s in a["strategies"]]
    assert means == sorted(means)
    assert sum(s["win_probability"] for s in a["strategies"]) == pytest.approx(1.0, abs=0.001)
    for s in a["strategies"]:
        assert s["p10_s"] <= s["mean_s"] <= s["p90_s"]


def test_simulation_ignores_future_laps():
    laps = synthetic_race_laps(1)
    before = simulate(laps, 30, "DDD", 10)
    altered = laps.copy()
    altered.loc[altered["lap"] > 10, "lap_time_s"] = 50.0
    altered.loc[altered["lap"] > 10, "pit_in"] = True
    assert simulate(altered, 30, "DDD", 10) == before


def test_runs_out_of_range_raises():
    with pytest.raises(ValueError):
        simulate(one_driver(), 57, "DDD", 15, runs=50)
