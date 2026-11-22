import numpy as np
import pandas as pd
import pytest

from augur import config
from augur.features import fuel_s_per_lap
from augur.models.degradation import StintFit, guarded_compound_slopes
from augur.positions import projected_deg
from augur.schema import LAP_COLUMNS


def stint_rows(driver: str, compound: str, slope: float, n_laps: int, total_laps: int = 57) -> list[dict]:
    """``n_laps`` clean laps of one stint whose fuel-corrected times rise by ``slope`` per lap."""
    fuel = fuel_s_per_lap(total_laps)
    rows = []
    for i in range(n_laps):
        lap = i + 1
        rows.append(
            {"driver": driver, "team": "T", "lap": lap,
             # fuel_corrected adds back fuel * (lap - 1); subtract it so the fit sees `slope`.
             "lap_time_s": 90.0 + slope * lap - fuel * (lap - 1),
             "session_time_s": 90.0 * lap, "stint": 1, "compound": compound, "tyre_life": lap,
             "pit_in": False, "pit_out": False, "track_status": "1", "is_accurate": True}
        )
    return rows


def frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=list(LAP_COLUMNS))


# --- Guarded compound slope ignores short stints ----------------------------------


def test_guarded_compound_slope_shrinks_toward_prior():
    laps = frame(stint_rows("AAA", "HARD", 0.41, 5) + stint_rows("BBB", "HARD", 0.06, 9)
                 + stint_rows("CCC", "HARD", 0.04, 10))
    assert config.DEG_SHRINK_STINTS == 3
    guarded = guarded_compound_slopes(laps, 57, {"HARD": 0.03})
    assert guarded["HARD"] == pytest.approx((2 * 0.05 + 3 * 0.03) / 5, abs=1e-6)  # 0.038


def test_guarded_slope_without_fits_is_prior_or_default_and_clamped():
    laps = frame(stint_rows("AAA", "SOFT", 0.9, 12))
    guarded = guarded_compound_slopes(laps, 57, {"MEDIUM": 0.07})
    assert guarded["MEDIUM"] == pytest.approx(0.07)
    assert guarded["HARD"] == pytest.approx(config.DEG_FALLBACK_S_PER_LAP["HARD"])
    assert guarded["SOFT"] == config.DEG_CAP_S_PER_LAP  # (0.9 + 3 * 0.085) / 4 is above the cap
    assert guarded_compound_slopes(laps, 57, {"HARD": -0.5})["HARD"] == 0.0


# --- Short or negative stint fit ------------------------------------------------------


def test_short_or_negative_stint_fit_uses_guarded_slope():
    guarded = {"HARD": 0.05}
    assert projected_deg(StintFit(-0.164, 98.0, 12, 1.6), "HARD", guarded) == 0.05
    assert projected_deg(StintFit(0.334, 98.0, 5, 0.2), "HARD", guarded) == 0.05


def test_trusted_own_slope_is_capped():
    assert projected_deg(StintFit(0.07, 98.0, 9, 0.2), "HARD", {"HARD": 0.05}) == 0.07
    assert projected_deg(StintFit(0.5, 98.0, 12, 0.2), "HARD", {"HARD": 0.05}) == config.DEG_CAP_S_PER_LAP


# --- Model delta fades ---------------------------------------------------------------


def test_model_delta_fades(monkeypatch):
    from augur.positions import DriverStart, _simulate

    monkeypatch.setattr(config, "FUEL_S_PER_KG", 0.0)
    monkeypatch.setattr(config, "MODEL_DELTA_DECAY", 0.5)
    monkeypatch.setattr(config, "PACE_OFFSET_SD_S", 0.0)
    s = DriverStart(code="AAA", laps_completed=10, time_s=0.0, base_s=90.0, delta_s=-2.0,
                    deg_s_per_lap=0.0, next_deg_s_per_lap=0.0, tyre_age=5, compound="HARD",
                    stops=False, noise_s=0.0)
    _, _, history = _simulate([s], 10, 13, 100, 0, 22.0, record=True)
    assert history[0, :, 0].tolist() == pytest.approx([88.0, 89.0, 89.5])


def test_base_is_recent_pace_plus_model_delta():
    from augur.positions import driver_starts
    from augur.predictions import predictions_at
    from test_positions import field, race_laps

    class ConstantDelta:
        name = "constant"

        def predict(self, rows):
            return [-2.0] * len(rows)

    laps = race_laps(field(4), total_laps=57, upto=20)
    starts = {s.code: s for s in driver_starts(laps, 57, 20, ConstantDelta())}
    for p in predictions_at(laps, 57, 20, ConstantDelta()):
        assert starts[p["code"]].base_s == pytest.approx(p["recent_pace_s"])
        assert starts[p["code"]].delta_s == pytest.approx(-2.0, abs=0.002)


# --- Uncertainty grows with laps remaining ------------------------------------------


def test_uncertainty_grows_with_laps_remaining(monkeypatch):
    from augur.positions import DriverStart, _simulate

    # Neutralised periods would close the 100 s gap; this checks the pace terms only.
    monkeypatch.setattr(config, "SC_PROB_PER_LAP", 0.0)
    monkeypatch.setattr(config, "VSC_PROB_PER_LAP", 0.0)

    def spread(lap: int) -> float:
        pair = [
            DriverStart(code=c, laps_completed=lap, time_s=t, base_s=90.0, deg_s_per_lap=0.0,
                        next_deg_s_per_lap=0.0, tyre_age=5, compound="HARD", stops=False, noise_s=0.2)
            for c, t in (("AAA", 0.0), ("BBB", 100.0))  # far apart: no dirty air
        ]
        time, _, _ = _simulate(pair, lap, 57, 2000, 0, 22.0)
        return float((time[:, 1] - time[:, 0]).std())

    long_run, short_run = spread(17), spread(52)  # 40 and 5 laps left
    assert long_run > short_run
    # Lap noise alone grows with sqrt(laps) (ratio 2.8); the per-run offset grows linearly.
    assert long_run / short_run > 4


def test_stop_onto_harder_compound_is_slower():
    from augur.positions import DriverStart, _simulate

    def finish(compound: str) -> float:
        s = DriverStart(code="AAA", laps_completed=10, time_s=0.0, base_s=90.0, deg_s_per_lap=0.0,
                        next_deg_s_per_lap=0.0, tyre_age=27, compound=compound, stops=True, noise_s=0.0)
        time, _, _ = _simulate([s], 10, 30, 200, 0, 22.0)
        return float(time.mean())

    # SOFT -> HARD changes pace by +1.0 s/lap, HARD -> MEDIUM by -0.4 s/lap after the stop.
    assert finish("SOFT") > finish("HARD")


# --- Finishing-position distribution -------------------------------------------------


@pytest.mark.parametrize("lap", [1, 20, 56, 57])
def test_distribution_sums(lap):
    from augur.positions import positions_at
    from test_positions import FrameFeed, field, race_laps

    out = positions_at(FrameFeed(race_laps(field(), total_laps=57), 57), lap)
    assert len(out) == 20
    for d in out:
        assert len(d["position_distribution"]) == 20
        assert sum(d["position_distribution"]) == pytest.approx(1.0, abs=0.001)
        assert d["position_distribution"][0] == pytest.approx(d["p_win"], abs=1e-6)
    for i in range(20):
        assert sum(d["position_distribution"][i] for d in out) == pytest.approx(1.0, abs=0.001)


# --- Neutralised periods -----------------------------------------------------------------


def _start(code, time_s, laps=10, stops=False, compound="HARD", tyre_age=5):
    from augur.positions import DriverStart

    return DriverStart(code=code, laps_completed=laps, time_s=time_s, base_s=90.0, deg_s_per_lap=0.0,
                       next_deg_s_per_lap=0.0, tyre_age=tyre_age, compound=compound, stops=stops, noise_s=0.0)


@pytest.fixture
def quiet(monkeypatch):
    """No pace offset and no fuel effect, so lap times are exact."""
    monkeypatch.setattr(config, "PACE_OFFSET_SD_S", 0.0)
    monkeypatch.setattr(config, "FUEL_S_PER_KG", 0.0)
    return monkeypatch


def test_safety_car_compresses_the_field(quiet):
    from augur.positions import _simulate

    quiet.setattr(config, "SC_PROB_PER_LAP", 1.0)
    quiet.setattr(config, "SC_PIT_PROB", 0.0)
    starts = [_start("P1", 0.0), _start("P2", 12.0), _start("P3", 30.0)]
    _, _, history = _simulate(starts, 10, 30, 50, 0, 22.0, record=True)
    after = np.array([0.0, 12.0, 30.0]) + history[:, 0, :]  # cumulative time after lap N+1
    assert ((after[:, 1] - after[:, 0]) <= config.SC_GAP_S + 1e-9).all()
    assert ((after[:, 1] - after[:, 0]) > 0).all() and ((after[:, 2] - after[:, 1]) > 0).all()
    assert history[:, 0, 0] == pytest.approx(90.0 * config.SC_LAP_FACTOR)  # leader's lap is slowed


def test_no_safety_cars(quiet):
    from augur.positions import NO_PERIOD, _simulate, sample_periods

    quiet.setattr(config, "SC_PROB_PER_LAP", 0.0)
    quiet.setattr(config, "VSC_PROB_PER_LAP", 0.0)
    _, kind = sample_periods(10, 57, 500, np.random.default_rng(0))
    assert (kind == NO_PERIOD).all()
    _, _, history = _simulate([_start("AAA", 0.0), _start("BBB", 50.0)], 10, 57, 100, 0, 22.0, record=True)
    assert history == pytest.approx(np.full_like(history, 90.0))


def test_period_rates_and_lengths():
    from augur.positions import SAFETY_CAR, VIRTUAL_SAFETY_CAR, sample_periods

    first, kind = sample_periods(0, 57, 20000, np.random.default_rng(1))
    sc, vsc = (kind == SAFETY_CAR).mean(), (kind == VIRTUAL_SAFETY_CAR).mean()
    # 55 candidate laps: P(SC first) = sum over laps; roughly 0.36 and 0.26 of runs.
    assert 0.30 < sc < 0.42 and 0.20 < vsc < 0.32
    assert ((first[kind > 0] >= 1) & (first[kind > 0] <= 55)).all()


def test_stop_taken_under_a_safety_car(quiet):
    from augur.positions import _simulate

    quiet.setattr(config, "SC_PROB_PER_LAP", 1.0)
    quiet.setattr(config, "SC_PIT_PROB", 1.0)
    quiet.setattr(config, "COMPOUND_PACE_OFFSET_S", {"SOFT": 0.0, "MEDIUM": 0.0, "HARD": 0.0})
    s = _start("MED", 0.0, laps=15, stops=True, compound="MEDIUM", tyre_age=10)
    _, _, history = _simulate([s], 15, 57, 200, 0, 22.0, record=True)
    # Lap 16 is the first safety-car lap: slowed lap plus the halved pit loss, every run.
    expected = 90.0 * config.SC_LAP_FACTOR + config.SC_PIT_LOSS_FACTOR * 22.0
    assert history[:, 0, 0] == pytest.approx(np.full(200, expected))
    assert (history[:, 1:, 0] < 22.0 + 90.0 * config.SC_LAP_FACTOR).all()  # no second stop
