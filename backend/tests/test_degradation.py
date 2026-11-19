import pandas as pd
import pytest

from augur.models.degradation import (
    compound_median_slopes,
    current_stint_degradation,
    fit_stint,
    is_cliff,
)
from augur.schema import LAP_COLUMNS


def test_steady_point_one_per_lap():
    fit = fit_stint([2, 3, 4, 5, 6], [95.0, 95.1, 95.2, 95.3, 95.4])
    assert round(fit.slope, 3) == 0.1
    assert fit.n == 5


def test_short_stint_is_null():
    assert fit_stint([2, 3, 4], [95.0, 95.1, 95.2]) is None


def test_last_two_laps_fall_off_is_cliff():
    life = list(range(1, 9))
    line = [95.0 + 0.05 * x for x in life]
    times = line[:6] + [line[6] + 1.2, line[7] + 1.5]
    assert is_cliff(life, times) is True


def test_one_slow_lap_only_is_not_cliff():
    life = list(range(1, 9))
    times = [95.0 + 0.05 * x for x in life]
    times[-1] += 1.5
    assert is_cliff(life, times) is False


def test_cliff_needs_six_clean_laps():
    assert is_cliff([1, 2, 3, 4, 5], [95.0, 95.0, 95.0, 97.0, 97.0]) is False


def _stint_laps(total=20):
    rows = []
    for lap in range(1, total + 1):
        rows.append(
            {
                "driver": "VER", "team": "Blue", "lap": lap,
                # raw times fall by the fuel effect so fuel-corrected times rise by 0.1 s/lap
                "lap_time_s": 95.0 + 0.1 * lap - 0.03 * 110 / 57 * (lap - 1),
                "session_time_s": 100.0 * lap, "stint": 1, "compound": "MEDIUM",
                "tyre_life": lap, "pit_in": False, "pit_out": False,
                "track_status": "1", "is_accurate": lap > 1,
            }
        )
    return pd.DataFrame(rows, columns=list(LAP_COLUMNS))


def test_current_stint_degradation_uses_fuel_corrected_times():
    deg = current_stint_degradation(_stint_laps(), total_laps=57)["VER"]
    assert deg["deg_s_per_lap"] == pytest.approx(0.1, abs=1e-3)
    assert deg["deg_laps"] == 19
    assert deg["cliff"] is False
    assert deg["compound"] == "MEDIUM"


def test_compound_median_slopes():
    assert compound_median_slopes(_stint_laps(), 57)["MEDIUM"] == pytest.approx(0.1, abs=1e-3)
