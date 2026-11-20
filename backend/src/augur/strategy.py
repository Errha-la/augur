"""Seeded Monte Carlo pit-strategy comparison for one driver at a replay lap.

Model of a simulated lap j (fuel-corrected pace at tyre age 0 = ``base``):
    lap_time(j) = base + deg * tyre_age(j) - fuel_s_per_lap * (j - 1) + noise
A pit stop adds the pit loss once and resets tyre age on the next compound.
Everything is computed from laps up to the replay lap only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median

import numpy as np
import pandas as pd

from augur import config
from augur.features import clean_mask, fuel_corrected, fuel_s_per_lap
from augur.models.degradation import compound_median_slopes, current_stint_degradation

NO_STOP = "no further stop"


def pit_name(pit_lap: int) -> str:
    return f"pit on lap {pit_lap}"


def next_compound(current: str | None) -> str:
    """Compound fitted at a simulated stop: HARD, or MEDIUM when already on HARD."""
    return "MEDIUM" if current == "HARD" else "HARD"


def candidate_strategies(laps: pd.DataFrame, total_laps: int, driver: str, lap: int) -> list[tuple[str, int | None]]:
    """(name, pit_lap) candidates; "no further stop" only after two dry compounds."""
    own = laps[(laps["driver"] == driver) & (laps["lap"] <= lap)]
    used = {c for c in own["compound"].dropna() if c in config.DRY_COMPOUNDS}
    out: list[tuple[str, int | None]] = []
    if len(used) >= 2:
        out.append((NO_STOP, None))
    for k in config.PIT_OFFSETS:
        if lap + k < total_laps - 1:
            out.append((pit_name(lap + k), lap + k))
    return out


def pit_loss(laps: pd.DataFrame) -> float | None:
    """Median observed pit cost: in-lap + out-lap - 2 x that driver's recent pace."""
    clean = laps.assign(is_clean=clean_mask(laps))
    costs = []
    for _, g in clean.sort_values(["driver", "lap"]).groupby("driver"):
        by_lap = {int(r.lap): r for r in g.itertuples(index=False)}
        for r in g[g["pit_in"].astype(bool)].itertuples(index=False):
            out_lap = by_lap.get(int(r.lap) + 1)
            if out_lap is None or pd.isna(r.lap_time_s) or pd.isna(out_lap.lap_time_s):
                continue
            before = g[(g["lap"] < r.lap) & g["is_clean"]]["lap_time_s"].tail(config.RECENT_PACE_LAPS)
            if before.empty:
                continue
            cost = float(r.lap_time_s) + float(out_lap.lap_time_s) - 2.0 * float(median(before))
            if cost > 0:
                costs.append(cost)
    return float(median(costs)) if costs else None


@dataclass(frozen=True)
class DriverState:
    base_s: float
    deg_s_per_lap: float
    tyre_age: int
    compound: str | None
    next_compound: str
    next_deg_s_per_lap: float
    noise_s: float


def deg_or_fallback(value, compound: str | None, race_medians: dict[str, float]) -> float:
    if value is not None and not math.isnan(value):
        return float(value)
    if compound in race_medians:
        return race_medians[compound]
    return config.DEG_FALLBACK_S_PER_LAP.get(compound or "", config.DEG_FALLBACK_S_PER_LAP["MEDIUM"])


def driver_state(laps: pd.DataFrame, total_laps: int, driver: str) -> DriverState | None:
    deg = current_stint_degradation(laps, total_laps).get(driver)
    if deg is None:
        return None
    medians = compound_median_slopes(laps, total_laps)
    compound = deg["compound"]
    fit = deg["fit"]
    current_deg = deg_or_fallback(None if fit is None else fit.slope, compound, medians)
    if fit is not None:
        base = fit.intercept
    else:
        own = laps[(laps["driver"] == driver) & clean_mask(laps)].tail(config.RECENT_PACE_LAPS)
        own = own[own["tyre_life"].notna()]
        if own.empty:
            return None
        fc = fuel_corrected(own["lap_time_s"].astype(float), own["lap"], total_laps)
        base = float(median(fc)) - current_deg * float(median(own["tyre_life"].astype(float)))
    nxt = next_compound(compound)
    return DriverState(
        base_s=float(base),
        deg_s_per_lap=current_deg,
        tyre_age=int(deg["tyre_life"] or 1),
        compound=compound,
        next_compound=nxt,
        next_deg_s_per_lap=deg_or_fallback(None, nxt, medians),
        noise_s=max(config.NOISE_MIN_S, fit.residual_std if fit is not None else 0.0),
    )


def _expected_time(state: DriverState, lap: int, total_laps: int, pit_lap: int | None, loss: float) -> float:
    fuel = fuel_s_per_lap(total_laps)
    total = 0.0
    for j in range(lap + 1, total_laps + 1):
        if pit_lap is None or j <= pit_lap:
            pace = state.base_s + state.deg_s_per_lap * (state.tyre_age + j - lap)
        else:
            pace = state.base_s + state.next_deg_s_per_lap * (j - pit_lap)
        total += pace - fuel * (j - 1)
    return total + (loss if pit_lap is not None else 0.0)


def simulate(
    laps: pd.DataFrame,
    total_laps: int,
    driver: str,
    lap: int,
    runs: int = config.STRATEGY_RUNS_DEFAULT,
    seed: int = config.STRATEGY_SEED_DEFAULT,
) -> dict:
    """{pit_loss_s, strategies: [{name, pit_lap, mean_s, p10_s, p90_s, win_probability}]} by mean."""
    if not config.STRATEGY_RUNS_MIN <= int(runs) <= config.STRATEGY_RUNS_MAX:
        raise ValueError(f"runs must be {config.STRATEGY_RUNS_MIN}..{config.STRATEGY_RUNS_MAX}")
    laps = laps[laps["lap"] <= lap]
    observed = pit_loss(laps)
    loss = observed if observed is not None else config.PIT_LOSS_FALLBACK_S
    result = {"pit_loss_s": round(loss, 3), "strategies": []}
    candidates = candidate_strategies(laps, total_laps, driver, lap)
    state = driver_state(laps, total_laps, driver)
    remaining = total_laps - lap
    if state is None or not candidates or remaining <= 0:
        return result

    rng = np.random.default_rng(seed)
    noise_sd = state.noise_s * math.sqrt(remaining)  # sum of `remaining` iid lap noises
    totals = np.empty((len(candidates), int(runs)))
    for i, (_, pit_lap) in enumerate(candidates):
        totals[i] = _expected_time(state, lap, total_laps, pit_lap, loss) + rng.normal(0.0, noise_sd, int(runs))
    wins = np.bincount(np.argmin(totals, axis=0), minlength=len(candidates)) / int(runs)

    rows = []
    for i, (name, pit_lap) in enumerate(candidates):
        rows.append(
            {
                "name": name,
                "pit_lap": pit_lap,
                "mean_s": round(float(totals[i].mean()), 3),
                "p10_s": round(float(np.percentile(totals[i], 10)), 3),
                "p90_s": round(float(np.percentile(totals[i], 90)), 3),
                "win_probability": round(float(wins[i]), 4),
            }
        )
    rows.sort(key=lambda s: (s["mean_s"], s["name"]))
    result["strategies"] = rows
    return result
