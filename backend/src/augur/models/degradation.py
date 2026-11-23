"""Linear stint degradation and performance-cliff detection.

Fits fuel-corrected clean lap time against tyre life for a stint. All
functions take laps already cut at the replay lap, so they only see the past.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
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


def guarded_compound_slopes(
    laps: pd.DataFrame, total_laps: int, prior: Mapping[str, float] | None = None
) -> dict[str, float]:
    """Per dry compound: the slope the simulators project when a driver's own fit is untrusted.

    ``(k * median + K * p) / (k + K)`` over the k single-compound stint fits with at least
    POSITION_DEG_MIN_FIT_LAPS clean laps, K = DEG_SHRINK_STINTS, p = the circuit prior for
    the compound (else DEG_FALLBACK_S_PER_LAP); p alone when k = 0; clamped to
    [0, DEG_CAP_S_PER_LAP]. Unlike :func:`compound_median_slopes`, short fresh stints
    cannot set the slope for the rest of the race.
    """
    prior = prior or {}
    by_compound: dict[str, list[float]] = {}
    for s in stint_slopes(laps, total_laps):
        if s["n"] >= config.POSITION_DEG_MIN_FIT_LAPS and not math.isnan(s["slope"]):
            by_compound.setdefault(s["compound"], []).append(s["slope"])
    out: dict[str, float] = {}
    for compound in config.DRY_COMPOUNDS:
        p = prior.get(compound)
        if p is None or math.isnan(p):
            p = config.DEG_FALLBACK_S_PER_LAP[compound]
        fits = by_compound.get(compound, [])
        k, big_k = len(fits), config.DEG_SHRINK_STINTS
        value = (k * float(median(fits)) + big_k * float(p)) / (k + big_k) if fits else float(p)
        out[compound] = min(config.DEG_CAP_S_PER_LAP, max(0.0, value))
    return out


def guarded_slope(compound: str | None, guarded: Mapping[str, float]) -> float:
    """Guarded slope of a compound; non-dry or unknown compounds use the MEDIUM value."""
    if compound in guarded:
        return guarded[compound]
    return guarded.get("MEDIUM", config.DEG_FALLBACK_S_PER_LAP["MEDIUM"])
