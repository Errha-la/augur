"""Leakage-safe lap features.

``build_feature_table`` turns normalized laps into one row per (driver,
target lap k). Every feature of target lap k is computed only from rows with
``lap < k``; the ``target_*`` label columns come from lap k itself and are
never model inputs.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from statistics import median

import numpy as np
import pandas as pd

from augur import config

# Model inputs, in order. Driver identity is deliberately absent.
FEATURE_COLUMNS: tuple[str, ...] = (
    "tyre_life",
    "stint",
    "compound",
    "lap_fraction",
    "laps_since_pit",
    "recent_pace_trend_s",
    "circuit_deg_prior_s",
    "team_pace_gap_s",
)

TABLE_COLUMNS: tuple[str, ...] = (
    "driver",
    "team",
    "target_lap",
    *FEATURE_COLUMNS,
    "recent_pace_s",
    "target_lap_time_s",
    "target_clean",
)


def fuel_s_per_lap(total_laps: int) -> float:
    """Seconds of fuel effect per lap: 0.03 s/kg * 110 kg / total_laps."""
    if isinstance(total_laps, bool) or not isinstance(total_laps, (int, np.integer)) or total_laps < 1:
        raise ValueError(f"total_laps must be a positive int, got {total_laps!r}")
    return config.FUEL_S_PER_KG * config.FUEL_LOAD_KG / int(total_laps)


def fuel_corrected(lap_time_s, lap, total_laps: int):
    """Lap time as if run with the full fuel load: ``lap_time_s + fuel * (lap - 1)``."""
    return lap_time_s + fuel_s_per_lap(total_laps) * (lap - 1)


def clean_mask(laps: pd.DataFrame) -> pd.Series:
    """True for clean laps.

    A clean lap has a lap time, lap > 1, no pit in/out, green track status,
    ``is_accurate``, a dry compound, and is at most ``OUTLIER_PCT`` percent
    slower than the fastest clean lap of the race on an earlier lap. Whether
    lap j is clean depends only on rows with lap <= j.

    The fastest earlier clean lap equals the fastest earlier lap that passes
    every other rule: that lap is never slower than its own reference, so the
    outlier rule cannot remove it.
    """
    if laps.empty:
        return pd.Series(False, index=laps.index, dtype=bool)
    time = pd.to_numeric(laps["lap_time_s"], errors="coerce")
    base = (
        time.notna()
        & (laps["lap"] > 1)
        & ~laps["pit_in"].fillna(False).astype(bool)
        & ~laps["pit_out"].fillna(False).astype(bool)
        & (laps["track_status"] == "1").fillna(False).astype(bool)
        & laps["is_accurate"].fillna(False).astype(bool)
        & laps["compound"].isin(config.DRY_COMPOUNDS)
    )
    per_lap_min = time[base].groupby(laps.loc[base, "lap"]).min()
    reference: dict[int, float] = {}
    running = math.inf
    for lap in sorted(int(x) for x in laps["lap"].unique()):
        reference[lap] = running
        if lap in per_lap_min.index:
            running = min(running, float(per_lap_min[lap]))
    threshold = laps["lap"].map(reference) * (1.0 + config.OUTLIER_PCT / 100.0)
    return (base & (time <= threshold)).astype(bool)


def _num(value) -> float:
    if value is None or pd.isna(value):
        return math.nan
    return float(value)


def _median(values) -> float:
    return float(median(values)) if values else math.nan


def build_feature_table(
    laps: pd.DataFrame,
    total_laps: int,
    prior: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """One row per driver and target lap k = (each lap the driver completed) + 1.

    ``prior`` maps compound -> ``circuit_deg_prior_s`` (missing compound -> null).
    """
    fuel_s_per_lap(total_laps)  # validates total_laps
    prior = dict(prior or {})
    if laps.empty:
        return pd.DataFrame(columns=list(TABLE_COLUMNS))

    df = laps.assign(is_clean=clean_mask(laps)).sort_values(["driver", "lap"], kind="stable")

    # Clean lap times by lap and by (lap, team) for the team pace window.
    all_by_lap: dict[int, list[float]] = defaultdict(list)
    team_by_lap: dict[tuple[int, object], list[float]] = defaultdict(list)
    clean_rows = df[df["is_clean"]]
    for lap, team, t in zip(clean_rows["lap"], clean_rows["team"], clean_rows["lap_time_s"], strict=True):
        all_by_lap[int(lap)].append(float(t))
        team_by_lap[(int(lap), team)].append(float(t))

    def team_gap(team, k: int) -> float:
        window = range(k - config.TEAM_PACE_WINDOW, k)
        field = [t for lap in window for t in all_by_lap.get(lap, ())]
        own = [t for lap in window for t in team_by_lap.get((lap, team), ())]
        if team is None or not field or not own:
            return math.nan
        return _median(own) - _median(field)

    out = []
    for driver, g in df.groupby("driver", sort=True):
        rows = list(g.itertuples(index=False))
        by_lap = {int(r.lap): r for r in rows}
        clean_times: list[float] = []
        last_pit_in: int | None = None
        for r in rows:
            if r.is_clean:
                clean_times.append(float(r.lap_time_s))
            if bool(r.pit_in):
                last_pit_in = int(r.lap)
            k = int(r.lap) + 1
            recent = clean_times[-config.RECENT_PACE_LAPS :]
            recent_pace = _median(recent) if len(recent) == config.RECENT_PACE_LAPS else math.nan
            trend = clean_times[-1] - recent_pace if not math.isnan(recent_pace) else math.nan
            tyre_life = _num(r.tyre_life)
            compound = r.compound if isinstance(r.compound, str) else None
            target = by_lap.get(k)
            out.append(
                {
                    "driver": driver,
                    "team": r.team,
                    "target_lap": k,
                    "tyre_life": tyre_life + 1.0 if not math.isnan(tyre_life) else math.nan,
                    "stint": _num(r.stint),
                    "compound": compound,
                    "lap_fraction": k / int(total_laps),
                    "laps_since_pit": float(k - last_pit_in if last_pit_in is not None else k),
                    "recent_pace_trend_s": trend,
                    "circuit_deg_prior_s": _num(prior.get(compound)) if compound else math.nan,
                    "team_pace_gap_s": team_gap(r.team, k),
                    "recent_pace_s": recent_pace,
                    "target_lap_time_s": _num(target.lap_time_s) if target is not None else math.nan,
                    "target_clean": bool(target.is_clean) if target is not None else False,
                }
            )
    return pd.DataFrame(out, columns=list(TABLE_COLUMNS))


def training_rows(table: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Rows usable for training or evaluation: clean target lap and known recent pace.

    Returns (features restricted to ``FEATURE_COLUMNS``, target delta in seconds).
    """
    ok = table["target_clean"].astype(bool) & table["recent_pace_s"].notna()
    rows = table[ok]
    delta = rows["target_lap_time_s"] - rows["recent_pace_s"]
    return rows[list(FEATURE_COLUMNS)].reset_index(drop=True), delta.reset_index(drop=True)
