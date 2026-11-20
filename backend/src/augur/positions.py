"""Full-field Monte Carlo simulation of the rest of a race from lap N.

For every driver, a simulated lap j > N takes
    base + deg * (tyre_age(j) - tyre_age_now) - fuel_s_per_lap * (j - N) + noise
where ``base`` is the predicted next lap time at lap N. A simulated pit stop
adds the pit loss on its lap and restarts tyre age on the next compound. A
driver ending a lap less than DIRTY_AIR_GAP_S behind the car ahead (same lap
count) loses DIRTY_AIR_PENALTY_S on the next lap. Finishing order per run is by
laps completed, then cumulative time.

Every input comes from ``feed.laps_until(N)``; nothing after lap N is read.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import median

import numpy as np
import pandas as pd

from augur import config
from augur.feed import RaceFeed
from augur.features import fuel_s_per_lap
from augur.models.base import LapTimeModel
from augur.models.degradation import compound_median_slopes, current_stint_degradation
from augur.predictions import predictions_at
from augur.state import race_state
from augur.strategy import deg_or_fallback, next_compound, pit_loss

# Large enough to dominate any race time when ordering by (laps desc, time asc).
_LAP_WEIGHT = 1e7


@dataclass(frozen=True)
class DriverStart:
    """One driver's state at lap N, as the simulator needs it."""

    code: str
    laps_completed: int
    time_s: float  # cumulative session time at the last completed lap
    base_s: float  # predicted next lap time
    deg_s_per_lap: float
    next_deg_s_per_lap: float
    tyre_age: int
    compound: str | None
    stops: bool  # True: one more simulated stop (two dry compounds not yet used)
    noise_s: float


def _validate(lap: int, total_laps: int, runs: int, seed: int) -> None:
    for name, value in (("lap", lap), ("total_laps", total_laps), ("runs", runs), ("seed", seed)):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise TypeError(f"{name} must be an int, got {value!r}")
    if not 1 <= lap <= total_laps:
        raise ValueError(f"lap must be 1..{total_laps}, got {lap}")
    if not config.POSITION_RUNS_MIN <= runs <= config.POSITION_RUNS_MAX:
        raise ValueError(f"runs must be {config.POSITION_RUNS_MIN}..{config.POSITION_RUNS_MAX}, got {runs}")
    if seed < 0:
        raise ValueError(f"seed must be >= 0, got {seed}")


def _base_paces(
    laps: pd.DataFrame, total_laps: int, lap: int, model: LapTimeModel | None, prior, codes: list[str]
) -> dict[str, float]:
    """Model prediction, else median of own laps after lap 1, else the field median."""
    out: dict[str, float] = {}
    if model is not None:
        for p in predictions_at(laps, total_laps, lap, model, prior):
            if p["predicted_next_lap_s"] is not None:
                out[p["code"]] = float(p["predicted_next_lap_s"])
    timed = laps[laps["lap_time_s"].notna()]
    after_one = timed[timed["lap"] > 1]
    for code in codes:
        if code not in out:
            own = after_one.loc[after_one["driver"] == code, "lap_time_s"]
            if not own.empty:
                out[code] = float(median(own.astype(float)))
    if out:
        field = float(median(out.values()))
    elif not timed.empty:
        # Only lap 1 so far: every car gets the same pace (design gap, recorded in tasks.md).
        field = float(median(timed["lap_time_s"].astype(float)))
    else:
        field = 90.0
    return {code: out.get(code, field) for code in codes}


def projected_deg(fit, compound: str | None, medians: Mapping[str, float]) -> float:
    """Degradation projected to the flag: own fit from enough clean laps, else the compound
    median or default; never negative (tyres do not get faster with age)."""
    trusted = fit is not None and fit.n >= config.POSITION_DEG_MIN_FIT_LAPS and fit.slope >= 0
    return max(0.0, deg_or_fallback(fit.slope if trusted else None, compound, medians))


def driver_starts(
    laps: pd.DataFrame,
    total_laps: int,
    lap: int,
    model: LapTimeModel | None = None,
    prior: Mapping[str, float] | None = None,
) -> list[DriverStart]:
    """State of every driver with at least one lap, in running order at lap N."""
    laps = laps[laps["lap"] <= lap]
    standings = race_state(laps, [], {"race_id": "", "total_laps": total_laps}, lap)["drivers"]
    codes = [d["code"] for d in standings if d["laps_completed"] > 0]
    base = _base_paces(laps, total_laps, lap, model, prior, codes)
    deg = current_stint_degradation(laps, total_laps)
    medians = compound_median_slopes(laps, total_laps)

    starts = []
    for code in codes:
        own = laps[laps["driver"] == code].sort_values("lap")
        times = own["session_time_s"].dropna()
        d = deg.get(code, {})
        fit = d.get("fit")
        compound = d.get("compound")
        used = {c for c in own["compound"].dropna() if c in config.DRY_COMPOUNDS}
        starts.append(
            DriverStart(
                code=code,
                laps_completed=int(own["lap"].max()),
                time_s=float(times.iloc[-1]) if not times.empty else math.inf,
                base_s=base[code],
                deg_s_per_lap=projected_deg(fit, compound, medians),
                next_deg_s_per_lap=max(0.0, deg_or_fallback(None, next_compound(compound), medians)),
                tyre_age=int(d.get("tyre_life") or 0),
                compound=compound,
                stops=len(used) < 2,
                noise_s=max(config.NOISE_MIN_S, fit.residual_std if fit is not None else 0.0),
            )
        )
    return starts


def sample_pit_laps(
    starts: list[DriverStart], lap: int, total_laps: int, runs: int, rng: np.random.Generator
) -> np.ndarray:
    """(runs, drivers) simulated stop lap; 0 means no stop.

    Stop lap = N + max(1, life - tyre_age) + U{-J..J}, clipped to [N+1, total_laps-1].
    """
    out = np.zeros((runs, len(starts)), dtype=np.int64)
    lo, hi = lap + 1, total_laps - 1
    jitter = rng.integers(-config.PIT_JITTER_LAPS, config.PIT_JITTER_LAPS + 1, size=(runs, len(starts)))
    if lo > hi:
        return out
    for i, s in enumerate(starts):
        if not s.stops:
            continue
        life = config.STINT_LIFE_LAPS.get(s.compound or "", config.STINT_LIFE_FALLBACK_LAPS)
        target = lap + max(1, life - s.tyre_age)
        out[:, i] = np.clip(target + jitter[:, i], lo, hi)
    return out


def simulate_finish(
    starts: list[DriverStart],
    lap: int,
    total_laps: int,
    runs: int,
    seed: int,
    loss_s: float,
) -> np.ndarray:
    """(runs, drivers) finishing positions, 1-based, from laps N+1..total_laps."""
    n = len(starts)
    rng = np.random.default_rng(seed + lap)
    pit = sample_pit_laps(starts, lap, total_laps, runs, rng)
    laps_done = np.tile(np.array([s.laps_completed for s in starts], dtype=float), (runs, 1))
    time = np.tile(np.array([s.time_s for s in starts], dtype=float), (runs, 1))
    base = np.array([s.base_s for s in starts])
    deg = np.array([s.deg_s_per_lap for s in starts])
    next_deg = np.array([s.next_deg_s_per_lap for s in starts])
    age_now = np.array([s.tyre_age for s in starts], dtype=float)
    noise_sd = np.array([s.noise_s for s in starts])
    fresh_base = base - deg * age_now  # pace on new tyres at the current fuel load
    fuel = fuel_s_per_lap(total_laps)
    penalty = np.zeros((runs, n))

    for j in range(lap + 1, total_laps + 1):
        stopped = (pit > 0) & (pit < j)
        age_after_stop = j - pit
        pace = np.where(
            stopped,
            fresh_base + next_deg * age_after_stop,
            base + deg * (j - lap),  # deg * (tyre_age(j) - tyre_age_now)
        )
        lap_time = pace - fuel * (j - lap) + rng.normal(0.0, 1.0, (runs, n)) * noise_sd + penalty
        lap_time = lap_time + np.where(pit == j, loss_s, 0.0)
        time = time + lap_time
        laps_done = laps_done + 1
        penalty = _dirty_air(time, laps_done)

    return _positions(time, laps_done)


def _dirty_air(time: np.ndarray, laps_done: np.ndarray) -> np.ndarray:
    """Penalty for the next lap: cars less than the gap behind the car ahead on the same lap."""
    order = np.argsort(time - laps_done * _LAP_WEIGHT, axis=1, kind="stable")
    t = np.take_along_axis(time, order, axis=1)
    lc = np.take_along_axis(laps_done, order, axis=1)
    close = np.zeros_like(t, dtype=bool)
    close[:, 1:] = (lc[:, 1:] == lc[:, :-1]) & (t[:, 1:] - t[:, :-1] < config.DIRTY_AIR_GAP_S)
    penalty = np.zeros_like(time)
    np.put_along_axis(penalty, order, np.where(close, config.DIRTY_AIR_PENALTY_S, 0.0), axis=1)
    return penalty


def _positions(time: np.ndarray, laps_done: np.ndarray) -> np.ndarray:
    order = np.argsort(time - laps_done * _LAP_WEIGHT, axis=1, kind="stable")
    pos = np.empty_like(order)
    np.put_along_axis(pos, order, np.arange(1, order.shape[1] + 1)[None, :].repeat(order.shape[0], 0), axis=1)
    return pos


def summarize(codes: list[str], positions: np.ndarray) -> list[dict]:
    """Per driver probabilities and position spread, ordered by expected position."""
    n = len(codes)
    rows = []
    for i, code in enumerate(codes):
        p = positions[:, i].astype(float)
        rows.append(
            {
                "code": code,
                "p_win": round(float(np.mean(p == 1)), 6),
                "p_podium": round(float(np.mean(p <= 3)), 6),
                "p_points": round(float(np.mean(p <= min(10, n))), 6),
                "expected_position": round(float(p.mean()), 3),
                "position_p10": round(float(np.percentile(p, 10)), 2),
                "position_p90": round(float(np.percentile(p, 90)), 2),
            }
        )
    rows.sort(key=lambda r: (r["expected_position"], r["code"]))
    return rows


def positions_at(
    feed: RaceFeed,
    lap: int,
    model: LapTimeModel | None = None,
    prior: Mapping[str, float] | None = None,
    runs: int = config.POSITION_RUNS_DEFAULT,
    seed: int = config.POSITION_SEED_DEFAULT,
) -> list[dict]:
    """Finishing-position probabilities per driver at lap N from ``feed.laps_until(N)`` only."""
    total = feed.total_laps
    _validate(lap, total, runs, seed)
    laps = feed.laps_until(lap)
    laps = laps[laps["lap"] <= lap]  # defensive: a feed must never return later laps
    starts = driver_starts(laps, total, lap, model, prior)
    if not starts:
        return []
    codes = [s.code for s in starts]
    if lap >= total:
        # Final lap: the actual order, with certain outcomes.
        actual = np.arange(1, len(codes) + 1)[None, :]
        return summarize(codes, actual)
    observed = pit_loss(laps)
    loss = observed if observed is not None else config.PIT_LOSS_FALLBACK_S
    return summarize(codes, simulate_finish(starts, lap, total, runs, seed, loss))
