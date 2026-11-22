import pandas as pd
import pytest

from augur.schema import LAP_COLUMNS
from augur.strategy import simulate, simulate_pit_laps


def one_driver(total=57, upto=15, deg=0.05, compound="MEDIUM"):
    rows = []
    for lap in range(1, upto + 1):
        rows.append(
            {"driver": "DDD", "team": "T", "lap": lap, "lap_time_s": 95.0 + deg * lap,
             "session_time_s": 95.0 * lap, "stint": 1, "compound": compound,
             "tyre_life": lap, "pit_in": False, "pit_out": False, "track_status": "1",
             "is_accurate": lap > 1}
        )
    return pd.DataFrame(rows, columns=list(LAP_COLUMNS))


# --- Pit-lap plan simulation ---------------------------------------------------


def test_same_numbers_as_the_comparison():
    laps = one_driver()
    plans = simulate_pit_laps(laps, 57, "DDD", 15, [18], runs=500, seed=3)
    comparison = simulate(laps, 57, "DDD", 15, runs=500, seed=3)
    pit18 = next(s for s in comparison["strategies"] if s["name"] == "pit on lap 18")
    plan = plans["plans"][0]
    assert plan["pit_lap"] == 18
    assert (plan["mean_s"], plan["p10_s"], plan["p90_s"]) == (pit18["mean_s"], pit18["p10_s"], pit18["p90_s"])
    assert plans["pit_loss_s"] == comparison["pit_loss_s"]


@pytest.mark.parametrize("pit_lap", [15, 14, 56, 57])
def test_pit_lap_out_of_range(pit_lap):
    with pytest.raises(ValueError):
        simulate_pit_laps(one_driver(), 57, "DDD", 15, [pit_lap])


def test_pit_lap_wrong_type():
    for bad in (True, 18.0, "18"):
        with pytest.raises(TypeError):
            simulate_pit_laps(one_driver(), 57, "DDD", 15, [bad])


def test_plans_keep_input_order_and_allow_no_stop():
    out = simulate_pit_laps(one_driver(), 57, "DDD", 15, [40, None, 16], runs=200)
    assert [p["pit_lap"] for p in out["plans"]] == [40, None, 16]
    for p in out["plans"]:
        assert p["p10_s"] <= p["mean_s"] <= p["p90_s"]


def test_no_driver_state_returns_no_plans():
    out = simulate_pit_laps(one_driver(), 57, "XXX", 15, [18])
    assert out["plans"] == []


# --- Reproducible Monte Carlo results ----------------------------------------


def test_shared_draws_decide_by_plan():
    # Strong degradation: the earliest stop gives the freshest tyres for longest and is
    # cheaper in every run, so with shared draws it wins every run.
    laps = one_driver(deg=0.4)
    out = simulate(laps, 57, "DDD", 15, runs=1000, seed=42)
    best = out["strategies"][0]
    assert best["pit_lap"] == 16
    assert best["win_probability"] == 1.0
    assert sum(s["win_probability"] for s in out["strategies"]) == pytest.approx(1.0, abs=0.001)


def test_same_seed_twice():
    laps = one_driver()
    assert simulate_pit_laps(laps, 57, "DDD", 15, [16, 20], seed=42) == simulate_pit_laps(
        laps, 57, "DDD", 15, [16, 20], seed=42
    )
    assert simulate(laps, 57, "DDD", 15, seed=42) == simulate(laps, 57, "DDD", 15, seed=42)


# --- Candidate pit strategies: compound pace offset ---------------------------


def test_harder_compound_costs_time():
    from augur import config
    from augur.strategy import DriverState, _expected_time

    def state(nxt):
        return DriverState(base_s=90.0, deg_s_per_lap=0.0, tyre_age=10, compound="MEDIUM",
                           next_compound=nxt, next_deg_s_per_lap=0.0, noise_s=0.2)

    assert config.COMPOUND_PACE_OFFSET_S["HARD"] == 0.4
    hard = _expected_time(state("HARD"), 15, 57, 20, 22.0)
    medium = _expected_time(state("MEDIUM"), 15, 57, 20, 22.0)
    assert hard - medium == pytest.approx(0.4 * (57 - 20))
