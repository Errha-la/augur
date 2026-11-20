import numpy as np
import pandas as pd
import pytest

from augur import config
from augur.positions import DriverStart, positions_at, sample_pit_laps, simulate_finish
from augur.schema import LAP_COLUMNS


class FrameFeed:
    """RaceFeed over an in-memory DataFrame."""

    def __init__(self, laps: pd.DataFrame, total_laps: int, race_id: str = "test") -> None:
        self.race_id = race_id
        self.total_laps = total_laps
        self._laps = laps

    def latest_lap(self) -> int:
        return self.total_laps

    def laps_until(self, lap: int) -> pd.DataFrame:
        return self._laps[self._laps["lap"] <= lap].reset_index(drop=True).copy()


def race_laps(
    drivers: dict[str, tuple[float, float]], total_laps: int, upto: int | None = None, pit_lap: int = 5, seed: int = 0
) -> pd.DataFrame:
    """Laps for {code: (pace, start offset s)}; every driver stops once (MEDIUM -> HARD) on ``pit_lap``."""
    rng = np.random.default_rng(seed)
    rows = []
    for code, (pace, offset) in drivers.items():
        session = offset
        for lap in range(1, (upto or total_laps) + 1):
            stint = 1 if lap <= pit_lap else 2
            t = pace + 0.03 * (lap if stint == 1 else lap - pit_lap) + rng.normal(0, 0.1)
            if lap == pit_lap:
                t += 20.0
            session += t
            rows.append(
                {
                    "driver": code, "team": f"T{code}", "lap": lap, "lap_time_s": t, "session_time_s": session,
                    "stint": stint, "compound": "MEDIUM" if stint == 1 else "HARD",
                    "tyre_life": lap if stint == 1 else lap - pit_lap,
                    "pit_in": lap == pit_lap, "pit_out": lap == pit_lap + 1, "track_status": "1",
                    "is_accurate": True,
                }
            )
    return pd.DataFrame(rows, columns=list(LAP_COLUMNS))


def field(n: int = 20, gap: float = 1.5) -> dict[str, tuple[float, float]]:
    return {f"D{i:02d}": (90.0 + 0.05 * i, gap * i) for i in range(n)}


def start(code, time_s, base_s, stops=False, compound="HARD", tyre_age=5, noise_s=0.0, laps=10):
    return DriverStart(
        code=code, laps_completed=laps, time_s=time_s, base_s=base_s, deg_s_per_lap=0.0,
        next_deg_s_per_lap=0.0, tyre_age=tyre_age, compound=compound, stops=stops, noise_s=noise_s,
    )


# --- Simulate the remaining race for every driver ---------------------------


def test_dominant_leader():
    laps = race_laps({"LEA": (90.0, 0.0), "SEC": (90.0, 30.0), "THI": (90.2, 35.0)}, total_laps=40, upto=37)
    out = positions_at(FrameFeed(laps, 40), 37)
    leader = next(d for d in out if d["code"] == "LEA")
    assert leader["p_win"] >= 0.95


def test_deterministic_per_lap():
    feed = FrameFeed(race_laps(field(), total_laps=57), 57)
    assert positions_at(feed, 20) == positions_at(feed, 20)


def test_altered_future_laps():
    laps = race_laps(field(), total_laps=57)
    before = positions_at(FrameFeed(laps, 57), 20)
    altered = laps.copy()
    future = altered["lap"] > 20
    altered.loc[future, "lap_time_s"] = 200.0
    altered.loc[future, "session_time_s"] = altered.loc[future, "session_time_s"] * 3
    altered.loc[future, "compound"] = "SOFT"
    assert positions_at(FrameFeed(altered, 57), 20) == before


def test_feed_returning_future_laps_is_ignored():
    laps = race_laps(field(), total_laps=57)

    class LeakyFeed(FrameFeed):
        def laps_until(self, lap):
            return self._laps.copy()

    assert positions_at(LeakyFeed(laps, 57), 20) == positions_at(FrameFeed(laps, 57), 20)


def test_seed_changes_results_and_invalid_inputs_fail():
    feed = FrameFeed(race_laps(field(), total_laps=57), 57)
    assert positions_at(feed, 20, seed=1) != positions_at(feed, 20, seed=2)
    for kwargs in ({"runs": 10}, {"runs": True}, {"seed": -1}):
        with pytest.raises((ValueError, TypeError)):
            positions_at(feed, 20, **kwargs)
    with pytest.raises(ValueError):
        positions_at(feed, 58)


# --- Expected pit plan --------------------------------------------------------


def test_stop_window_medium_age_10_lap_15_of_57():
    s = start("MED", 0.0, 90.0, stops=True, compound="MEDIUM", tyre_age=10, laps=15)
    pits = sample_pit_laps([s], 15, 57, 2000, np.random.default_rng(0))
    assert pits.min() >= 30 and pits.max() <= 36
    assert set(np.unique(pits)) == set(range(30, 37))


def test_next_compound_after_medium_is_hard():
    from augur.strategy import next_compound

    assert next_compound("MEDIUM") == "HARD"
    assert next_compound("SOFT") == "HARD"
    assert next_compound("HARD") == "MEDIUM"


def test_two_compounds_used_means_no_stop():
    laps = race_laps(field(5), total_laps=57, upto=30, pit_lap=10)
    from augur.positions import driver_starts

    starts = driver_starts(laps, 57, 30)
    assert all(not s.stops for s in starts)
    pits = sample_pit_laps(starts, 30, 57, 500, np.random.default_rng(0))
    assert (pits == 0).all()


def test_stop_adds_pit_loss():
    a = start("AAA", 0.0, 90.0, stops=True, compound="MEDIUM", tyre_age=27, laps=10)
    b = start("BBB", 5.0, 90.0, laps=10)
    pos = simulate_finish([a, b], 10, 20, 200, 0, loss_s=22.0)
    assert (pos[:, 0] == 2).all()


# --- Dirty-air penalty -------------------------------------------------------


def test_slightly_faster_car_stays_behind():
    ahead = start("AHD", 0.0, 90.0)
    chaser = start("CHS", 0.5, 89.8)
    pos = simulate_finish([ahead, chaser], 10, 20, 100, 0, loss_s=22.0)
    assert (pos[:, 0] == 1).all() and (pos[:, 1] == 2).all()


def test_much_faster_car_passes():
    ahead = start("AHD", 0.0, 90.0)
    chaser = start("CHS", 0.5, 89.0)
    pos = simulate_finish([ahead, chaser], 10, 20, 100, 0, loss_s=22.0)
    assert (pos[:, 1] == 1).all()


# --- Finishing-position probabilities ----------------------------------------


@pytest.mark.parametrize("lap", [1, 2, 20, 56])
def test_probability_sums(lap):
    out = positions_at(FrameFeed(race_laps(field(), total_laps=57), 57), lap)
    assert len(out) == 20
    assert abs(sum(d["p_win"] for d in out) - 1) < 0.001
    assert abs(sum(d["p_podium"] for d in out) - 3) < 0.001
    assert abs(sum(d["p_points"] for d in out) - 10) < 0.001
    assert [d["expected_position"] for d in out] == sorted(d["expected_position"] for d in out)
    # The mean may fall outside p10..p90 for a skewed distribution; only the range is ordered.
    assert all(1 <= d["position_p10"] <= d["position_p90"] <= 20 for d in out)
    assert all(1 <= d["expected_position"] <= 20 for d in out)
    assert set(out[0]) == {
        "code", "p_win", "p_podium", "p_points", "expected_position", "position_p10", "position_p90"
    }


def test_final_lap_is_the_actual_order():
    laps = race_laps(field(5), total_laps=57)
    out = positions_at(FrameFeed(laps, 57), 57)
    assert [d["code"] for d in out] == [f"D{i:02d}" for i in range(5)]
    for i, d in enumerate(out, start=1):
        assert d["p_win"] == (1.0 if i == 1 else 0.0)
        assert d["p_podium"] == (1.0 if i <= 3 else 0.0)
        assert d["p_points"] == 1.0
        assert d["expected_position"] == d["position_p10"] == d["position_p90"] == i
