"""Linear stint degradation and performance-cliff detection.

Fits fuel-corrected clean lap time against tyre life for a stint. All
functions take laps already cut at the replay lap, so they only see the past.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median

import numpy as np
import pandas as pd

from augur import config
from augur.features import clean_mask, fuel_corrected


@dataclass(frozen=True)
class StintFit:
    slope: float  # deg_s_per_lap
    intercept: float  # fuel-corrected lap time at tyre_life 0
    n: int
    residual_std: float


def fit_line(x, y) -> tuple[float, float]:
    """Least-squares (slope, intercept) of y against x."""
    xs = np.asarray(x, dtype=float)
    ys = np.asarray(y, dtype=float)
    if len(xs) < 2 or np.ptp(xs) == 0:
        raise ValueError("need at least two distinct x values")
    slope, intercept = np.polyfit(xs, ys, 1)
    return float(slope), float(intercept)


def fit_stint(tyre_life, times) -> StintFit | None:
    """Fit a stint's clean laps; None when fewer than MIN_STINT_LAPS laps."""
    xs = np.asarray(tyre_life, dtype=float)
    ys = np.asarray(times, dtype=float)
    if len(xs) < config.MIN_STINT_LAPS or np.ptp(xs) == 0:
        return None
    slope, intercept = fit_line(xs, ys)
    residuals = ys - (intercept + slope * xs)
    return StintFit(slope, intercept, len(xs), float(np.std(residuals)))


def is_cliff(tyre_life, times) -> bool:
    """Both of the last 2 clean laps are > CLIFF_RESIDUAL_S above the line of the earlier laps."""
    xs = np.asarray(tyre_life, dtype=float)
    ys = np.asarray(times, dtype=float)
    if len(xs) < config.CLIFF_MIN_LAPS or np.ptp(xs[:-2]) == 0:
        return False
    slope, intercept = fit_line(xs[:-2], ys[:-2])
    residuals = ys[-2:] - (intercept + slope * xs[-2:])
    return bool(np.all(residuals > config.CLIFF_RESIDUAL_S))


def _clean_stints(laps: pd.DataFrame, total_laps: int) -> pd.DataFrame:
    """Clean laps with a tyre life, plus their fuel-corrected time."""
    df = laps[clean_mask(laps)]
    df = df[df["tyre_life"].notna() & df["stint"].notna()]
    return df.assign(
        fc_time=fuel_corrected(df["lap_time_s"].astype(float), df["lap"], total_laps)
    ).sort_values(["driver", "lap"], kind="stable")


def current_stint_degradation(laps: pd.DataFrame, total_laps: int) -> dict[str, dict]:
    """Per driver: degradation of the stint of their latest row.

    Returns ``{code: {stint, compound, tyre_life, deg_s_per_lap, deg_laps, cliff, fit}}``;
    ``deg_s_per_lap`` is None below MIN_STINT_LAPS clean laps.
    """
    if laps.empty:
        return {}
    clean = _clean_stints(laps, total_laps)
    out: dict[str, dict] = {}
    for driver, g in laps.sort_values(["driver", "lap"], kind="stable").groupby("driver", sort=True):
        last = g.iloc[-1]
        stint = last["stint"]
        compound = last["compound"] if isinstance(last["compound"], str) else None
        tyre_life = None if pd.isna(last["tyre_life"]) else int(last["tyre_life"])
        if pd.isna(stint):
            stint_clean = clean.iloc[0:0]
        else:
            stint_clean = clean[(clean["driver"] == driver) & (clean["stint"] == stint)]
        fit = fit_stint(stint_clean["tyre_life"], stint_clean["fc_time"])
        out[str(driver)] = {
            "stint": None if pd.isna(stint) else int(stint),
            "compound": compound,
            "tyre_life": tyre_life,
            "deg_s_per_lap": None if fit is None else round(fit.slope, 4),
            "deg_laps": int(len(stint_clean)),
            "cliff": is_cliff(stint_clean["tyre_life"], stint_clean["fc_time"]),
            "fit": fit,
        }
    return out


def stint_slopes(laps: pd.DataFrame, total_laps: int) -> list[dict]:
    """Every (driver, stint) with a fit: {driver, stint, compound, slope, n}."""
    clean = _clean_stints(laps, total_laps)
    out = []
    for (driver, stint), g in clean.groupby(["driver", "stint"], sort=True):
        compounds = g["compound"].dropna().unique()
        fit = fit_stint(g["tyre_life"], g["fc_time"])
        if fit is None or len(compounds) != 1:
            continue
        out.append(
            {"driver": driver, "stint": int(stint), "compound": str(compounds[0]), "slope": fit.slope, "n": fit.n}
        )
    return out


def compound_median_slopes(laps: pd.DataFrame, total_laps: int) -> dict[str, float]:
    """Median stint slope per dry compound over all fitted stints."""
    by_compound: dict[str, list[float]] = {}
    for s in stint_slopes(laps, total_laps):
        by_compound.setdefault(s["compound"], []).append(s["slope"])
    return {c: float(median(v)) for c, v in sorted(by_compound.items()) if v and not math.isnan(median(v))}
