"""Full-field Monte Carlo simulation of the rest of a race from lap N.

For every driver, a simulated lap j > N takes
    base + delta * MODEL_DELTA_DECAY ** (j - N - 1) + deg * (tyre_age(j) - tyre_age_now)
        - fuel_s_per_lap * (j - N) + noise
where ``base`` is the driver's recent pace at lap N and ``delta`` the lap-time model's
predicted change for lap N+1, which fades instead of lasting to the flag. Each run
also draws one pace offset per driver (PACE_OFFSET_SD_S) that lasts the whole run, and
a simulated stop changes pace by the compound offset (COMPOUND_PACE_OFFSET_S). A run may
contain one safety car or virtual safety car period (``sample_periods``): its laps are
slower by the same amount for every car, have no dirty air and cheaper stops, a safety car closes the gaps, and a driver
still due a stop usually takes it at the start of the period. A simulated pit stop
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
from augur.models.degradation import current_stint_degradation, guarded_compound_slopes, guarded_slope
from augur.predictions import predictions_at
from augur.state import race_state
from augur.strategy import compound_offset, next_compound, pit_loss

# Large enough to dominate any race time when ordering by (laps desc, time asc).
_LAP_WEIGHT = 1e7


@dataclass(frozen=True)
class DriverStart:
    """One driver's state at lap N, as the simulator needs it."""

    code: str
    laps_completed: int
    time_s: float  # cumulative session time at the last completed lap
    base_s: float  # recent pace (median of the last clean laps), else a fallback pace
    deg_s_per_lap: float
    next_deg_s_per_lap: float
    tyre_age: int
    compound: str | None
    stops: bool  # True: one more simulated stop (two dry compounds not yet used)
    noise_s: float
    delta_s: float = 0.0  # model's next-lap delta from base_s; decays by MODEL_DELTA_DECAY per lap


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
) -> dict[str, tuple[float, float]]:
    """code -> (base pace, model delta for lap N+1).

    With a model prediction the base is the driver's recent pace (median of the last clean
    laps) and the delta is ``predicted_next_lap_s - recent_pace_s``; otherwise the base is
    the median of own laps after lap 1, else the field median, and the delta is 0.
    """
    out: dict[str, tuple[float, float]] = {}
    if model is not None:
        for p in predictions_at(laps, total_laps, lap, model, prior):
            if p["predicted_next_lap_s"] is not None and p["recent_pace_s"] is not None:
                recent = float(p["recent_pace_s"])
                out[p["code"]] = (recent, float(p["predicted_next_lap_s"]) - recent)
    timed = laps[laps["lap_time_s"].notna()]
    after_one = timed[timed["lap"] > 1]
    for code in codes:
        if code not in out:
            own = after_one.loc[after_one["driver"] == code, "lap_time_s"]
            if not own.empty:
                out[code] = (float(median(own.astype(float))), 0.0)
    if out:
        field = float(median(b for b, _ in out.values()))
    elif not timed.empty:
        # Only lap 1 so far: every car gets the same pace (design gap, recorded in tasks.md).
        field = float(median(timed["lap_time_s"].astype(float)))
    else:
        field = 90.0
    return {code: out.get(code, (field, 0.0)) for code in codes}


def projected_deg(fit, compound: str | None, guarded: Mapping[str, float]) -> float:
    """Degradation projected to the flag: own fit from enough clean laps with a non-negative
    slope, else the guarded compound slope; always within [0, DEG_CAP_S_PER_LAP]."""
    trusted = fit is not None and fit.n >= config.POSITION_DEG_MIN_FIT_LAPS and fit.slope >= 0
    value = fit.slope if trusted else guarded_slope(compound, guarded)
    return min(config.DEG_CAP_S_PER_LAP, max(0.0, float(value)))


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
    guarded = guarded_compound_slopes(laps, total_laps, prior)

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
                base_s=base[code][0],
                delta_s=base[code][1],
                deg_s_per_lap=projected_deg(fit, compound, guarded),
                next_deg_s_per_lap=projected_deg(None, next_compound(compound), guarded),
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


# Neutralised period kinds in ``sample_periods``.
NO_PERIOD, SAFETY_CAR, VIRTUAL_SAFETY_CAR = 0, 1, 2


def sample_periods(lap: int, total_laps: int, runs: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """(runs,) first lap and kind of the run's single neutralised period (0 / NO_PERIOD: none).

    For each lap j in N+1..total_laps-2 a safety car starts with probability SC_PROB_PER_LAP,
    otherwise a virtual safety car with VSC_PROB_PER_LAP, until one has started.
    """
    first = np.full(runs, total_laps + 1, dtype=np.int64)
    kind = np.zeros(runs, dtype=np.int64)
    laps = np.arange(lap + 1, total_laps - 1)  # N+1 .. total_laps-2
    if len(laps) == 0:
        return np.zeros(runs, dtype=np.int64), kind
    u = rng.random((runs, len(laps)))
    p_sc = config.SC_PROB_PER_LAP
    p_vsc = (1.0 - p_sc) * config.VSC_PROB_PER_LAP
    started = u < p_sc + p_vsc
    any_start = started.any(axis=1)
    idx = np.argmax(started, axis=1)
    first[any_start] = laps[idx[any_start]]
    hit_u = u[np.arange(runs), idx]
    kind[any_start] = np.where(hit_u[any_start] < p_sc, SAFETY_CAR, VIRTUAL_SAFETY_CAR)
    first[~any_start] = 0
    return first, kind


def _compress(time: np.ndarray, laps_done: np.ndarray, rows: np.ndarray) -> np.ndarray:
    """Copy of ``time`` where, in ``rows``, every gap to the car ahead on the same lap count is
    at most SC_GAP_S, keeping the order."""
    out = time.copy()
    for r in np.flatnonzero(rows):
        order = np.argsort(time[r] - laps_done[r] * _LAP_WEIGHT, kind="stable")
        t, lc = time[r, order], laps_done[r, order]
        new = t.copy()
        for k in range(1, len(t)):
            # Cars without a timed lap (time inf) stay where they are, out of the chain.
            if lc[k] == lc[k - 1] and np.isfinite(t[k]) and np.isfinite(t[k - 1]):
                new[k] = new[k - 1] + min(t[k] - t[k - 1], config.SC_GAP_S)
        out[r, order] = new
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
    time, laps_done, _ = _simulate(starts, lap, total_laps, runs, seed, loss_s)
    return _positions(time, laps_done)


def _simulate(
    starts: list[DriverStart],
    lap: int,
    total_laps: int,
    runs: int,
    seed: int,
    loss_s: float,
    record: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """(cumulative time, laps completed) per (run, driver) at the flag, plus with ``record``
    the (runs, laps, drivers) lap times of laps N+1..total_laps."""
    n = len(starts)
    rng = np.random.default_rng(seed + lap)
    pit = sample_pit_laps(starts, lap, total_laps, runs, rng)
    sc_first, sc_kind = sample_periods(lap, total_laps, runs, rng)
    sc_len = np.where(sc_kind == SAFETY_CAR, config.SC_LAPS, np.where(sc_kind == VIRTUAL_SAFETY_CAR, config.VSC_LAPS, 0))
    sc_last = sc_first + sc_len - 1  # truncated at the flag by the lap loop
    loss_factor = np.where(sc_kind == SAFETY_CAR, config.SC_PIT_LOSS_FACTOR, config.VSC_PIT_LOSS_FACTOR)
    # A driver whose sampled stop comes after the period starts takes it on the period's
    # first lap with probability SC_PIT_PROB (a cheaper stop).
    move = (sc_kind[:, None] != NO_PERIOD) & (pit > sc_first[:, None]) & (rng.random((runs, n)) < config.SC_PIT_PROB)
    pit = np.where(move, sc_first[:, None], pit)
    laps_done = np.tile(np.array([s.laps_completed for s in starts], dtype=float), (runs, 1))
    time = np.tile(np.array([s.time_s for s in starts], dtype=float), (runs, 1))
    base = np.array([s.base_s for s in starts])
    delta = np.array([s.delta_s for s in starts])
    # Neutralised laps add the same slowdown to every car, (factor - 1) x the field's median
    # pace, so a virtual safety car keeps the gaps and a safety car only closes them.
    field_pace = float(np.median(base)) if n else 0.0
    slowdown = np.where(sc_kind == SAFETY_CAR, config.SC_LAP_FACTOR - 1.0, config.VSC_LAP_FACTOR - 1.0) * field_pace
    deg = np.array([s.deg_s_per_lap for s in starts])
    next_deg = np.array([s.next_deg_s_per_lap for s in starts])
    age_now = np.array([s.tyre_age for s in starts], dtype=float)
    noise_sd = np.array([s.noise_s for s in starts])
    # Pace on new tyres of the next compound at the current fuel load: the current
    # compound's wear removed, plus the offset between the two compounds.
    switch = np.array([compound_offset(next_compound(s.compound)) - compound_offset(s.compound) for s in starts])
    fresh_base = base - deg * age_now + switch
    # One pace offset per run and driver for the whole run: uncertainty about a driver's
    # pace that does not average out over the laps remaining.
    offset = rng.normal(0.0, config.PACE_OFFSET_SD_S, (runs, n))
    fuel = fuel_s_per_lap(total_laps)
    penalty = np.zeros((runs, n))
    history = np.empty((runs, total_laps - lap, n)) if record else None

    for j in range(lap + 1, total_laps + 1):
        stopped = (pit > 0) & (pit < j)
        age_after_stop = j - pit
        pace = np.where(
            stopped,
            fresh_base + next_deg * age_after_stop,
            # deg * (tyre_age(j) - tyre_age_now); the model's next-lap delta fades lap by lap
            base + delta * config.MODEL_DELTA_DECAY ** (j - lap - 1) + deg * (j - lap),
        )
        neutral = (sc_kind != NO_PERIOD) & (sc_first <= j) & (j <= sc_last)  # (runs,)
        lap_time = pace + offset - fuel * (j - lap) + rng.normal(0.0, 1.0, (runs, n)) * noise_sd
        # Neutralised laps: slower by the period's factor, no dirty air, cheaper stops.
        lap_time = np.where(neutral[:, None], lap_time + slowdown[:, None], lap_time + penalty)
        stop_loss = np.where(neutral, loss_s * loss_factor, loss_s)
        lap_time = lap_time + np.where(pit == j, stop_loss[:, None], 0.0)
        new_time = time + lap_time
        laps_done = laps_done + 1
        bunch = (sc_kind == SAFETY_CAR) & (sc_first == j)
        if bunch.any():
            # End of a safety car's first lap: the field closes up behind it.
            new_time = _compress(new_time, laps_done, bunch)
        if history is not None:
            history[:, j - lap - 1, :] = new_time - time
        time = new_time
        penalty = _dirty_air(time, laps_done)

    return time, laps_done, history


def _dirty_air(time: np.ndarray, laps_done: np.ndarray) -> np.ndarray:
    """Penalty for the next lap: cars less than the gap behind the car ahead on the same lap."""
    order = np.argsort(time - laps_done * _LAP_WEIGHT, axis=1, kind="stable")
    t = np.take_along_axis(time, order, axis=1)
    lc = np.take_along_axis(laps_done, order, axis=1)
    close = np.zeros_like(t, dtype=bool)
    # Two untimed cars (time inf) give inf - inf = nan, which compares False: no penalty.
    with np.errstate(invalid="ignore"):
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
    """Per driver probabilities, position spread, and finishing-position distribution,
    ordered by expected position."""
    n = len(codes)
    rows = []
    for i, code in enumerate(codes):
        p = positions[:, i].astype(float)
        counts = np.bincount(positions[:, i].astype(np.int64) - 1, minlength=n)[:n]
        rows.append(
            {
                "code": code,
                "p_win": round(float(np.mean(p == 1)), 6),
                "p_podium": round(float(np.mean(p <= 3)), 6),
                "p_points": round(float(np.mean(p <= min(10, n))), 6),
                "expected_position": round(float(p.mean()), 3),
                "position_p10": round(float(np.percentile(p, 10)), 2),
                "position_p90": round(float(np.percentile(p, 90)), 2),
                # Share of runs finishing P1..Pn.
                "position_distribution": [round(float(c) / len(p), 6) for c in counts],
            }
        )
    rows.sort(key=lambda r: (r["expected_position"], r["code"]))
    return rows


def prepare(
    feed: RaceFeed,
    lap: int,
    model: LapTimeModel | None = None,
    prior: Mapping[str, float] | None = None,
) -> tuple[list[DriverStart], float]:
    """(driver states, pit loss) at lap N from ``feed.laps_until(N)`` only.

    Shared by :func:`positions_at` and ``augur.tune_sim``, which simulates one prepared
    lap with several constant settings.
    """
    laps = feed.laps_until(lap)
    laps = laps[laps["lap"] <= lap]  # defensive: a feed must never return later laps
    starts = driver_starts(laps, feed.total_laps, lap, model, prior)
    observed = pit_loss(laps)
    return starts, observed if observed is not None else config.PIT_LOSS_FALLBACK_S


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
    starts, loss = prepare(feed, lap, model, prior)
    if not starts:
        return []
    codes = [s.code for s in starts]
    if lap >= total:
        # Final lap: the actual order, with certain outcomes.
        actual = np.arange(1, len(codes) + 1)[None, :]
        return summarize(codes, actual)
    return summarize(codes, simulate_finish(starts, lap, total, runs, seed, loss))
