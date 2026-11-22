"""Data behind the strategy charts, computed only from the laps it is given.

Every function takes laps already cut at the replay lap N (rows beyond N are
dropped defensively) and returns plain JSON-ready dicts. Routes in
``augur.api`` validate input, open the feed and call these.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from statistics import median
from typing import Any

import pandas as pd

from augur import config
from augur.features import clean_mask, fuel_corrected
from augur.state import race_state, to_json_value
from augur.strategy import pit_loss

# Fewest points the degradation chart fits a line through.
DEG_FIT_MIN_POINTS = 4


def _r(value: float) -> float:
    return round(float(value), 3)


def race_trace(
    laps: pd.DataFrame,
    drivers: Iterable[Mapping[str, Any]],
    race_meta: Mapping[str, Any],
    lap: int,
) -> dict:
    """Each driver's time gained (+) or lost (−) against a reference pace per lap.

    Race time = session time − race start; race start = median over drivers of
    lap-1 session time − lap-1 lap time. ``reference_lap_s`` = median over
    drivers of race time at their last timed lap / that lap number.
    """
    laps = laps[laps["lap"] <= lap]
    state = race_state(laps, drivers, race_meta, lap)

    first = laps[(laps["lap"] == 1) & laps["session_time_s"].notna() & laps["lap_time_s"].notna()]
    starts = (first["session_time_s"].astype(float) - first["lap_time_s"].astype(float)).tolist()
    race_start = float(median(starts)) if starts else None

    times: dict[str, list[tuple[int, float]]] = {}
    if race_start is not None:
        timed = laps[laps["session_time_s"].notna()].sort_values(["driver", "lap"], kind="stable")
        for code, n, t in zip(timed["driver"], timed["lap"], timed["session_time_s"]):
            times.setdefault(code, []).append((int(n), float(t) - race_start))

    paces = [pts[-1][1] / pts[-1][0] for pts in times.values() if pts]
    reference = float(median(paces)) if paces else None

    out = []
    for d in state["drivers"]:
        pts = times.get(d["code"], []) if reference is not None else []
        out.append(
            {
                "code": d["code"],
                "team_color": d["team_color"],
                "points": [{"lap": n, "delta_s": _r(reference * n - t)} for n, t in pts],
            }
        )
    return {
        "race_id": race_meta["race_id"],
        "lap": lap,
        "reference_lap_s": None if reference is None else _r(reference),
        "drivers": out,
    }


def rejoin_slot(cars: list[dict], driver: str, pit_loss_s: float) -> dict | None:
    """Where ``driver`` would rejoin if it pitted now; other cars assumed not to pit.

    ``cars`` are ``{code, gap_to_leader_s}`` with a gap. Null when ``driver`` has no gap.
    """
    own = next((c for c in cars if c["code"] == driver), None)
    if own is None:
        return None
    projected = own["gap_to_leader_s"] + pit_loss_s
    others = [c for c in cars if c["code"] != driver]
    ahead = [c for c in others if c["gap_to_leader_s"] <= projected]
    behind = [c for c in others if c["gap_to_leader_s"] > projected]
    a = max(ahead, key=lambda c: c["gap_to_leader_s"]) if ahead else None
    b = min(behind, key=lambda c: c["gap_to_leader_s"]) if behind else None
    return {
        "position": 1 + len(ahead),
        "gap_to_leader_s": _r(projected),
        "ahead": a["code"] if a else None,
        "ahead_gap_s": _r(projected - a["gap_to_leader_s"]) if a else None,
        "behind": b["code"] if b else None,
        "behind_gap_s": _r(b["gap_to_leader_s"] - projected) if b else None,
    }


def _lap_length(laps: pd.DataFrame, leader: str | None) -> float | None:
    """Leader's last lap when clean, else median of the leader's clean laps, else of all laps."""
    clean = laps[clean_mask(laps)]
    if leader is not None:
        own = laps[laps["driver"] == leader].sort_values("lap")
        if not own.empty and own.index[-1] in clean.index:
            return _r(own["lap_time_s"].iloc[-1])
        own_clean = clean[clean["driver"] == leader]["lap_time_s"].dropna()
        if not own_clean.empty:
            return _r(median(own_clean.astype(float)))
    times = laps["lap_time_s"].dropna()
    return _r(median(times.astype(float))) if not times.empty else None


def rejoin(
    laps: pd.DataFrame,
    drivers: Iterable[Mapping[str, Any]],
    race_meta: Mapping[str, Any],
    lap: int,
    driver: str,
) -> dict:
    """Every car's gap to the leader at lap N and ``driver``'s rejoin slot (pit-stop clock)."""
    laps = laps[laps["lap"] <= lap]
    state = race_state(laps, drivers, race_meta, lap)
    observed = pit_loss(laps)
    loss = observed if observed is not None else config.PIT_LOSS_FALLBACK_S
    cars = [
        {
            "code": d["code"],
            "position": d["position"],
            "gap_to_leader_s": d["gap_to_leader_s"],
            "laps_behind_leader": d["laps_behind_leader"],
        }
        for d in state["drivers"]
        if d["gap_to_leader_s"] is not None
    ]
    leader = state["drivers"][0]["code"] if cars else None
    return {
        "race_id": race_meta["race_id"],
        "lap": lap,
        "driver": driver,
        "pit_loss_s": _r(loss),
        "lap_length_s": _lap_length(laps, leader),
        "cars": cars,
        "rejoin": rejoin_slot(cars, driver, loss),
    }


def stints(
    laps: pd.DataFrame,
    drivers: Iterable[Mapping[str, Any]],
    race_meta: Mapping[str, Any],
    lap: int,
) -> dict:
    """Each driver's stints so far, drivers in running order at lap N."""
    laps = laps[laps["lap"] <= lap]
    state = race_state(laps, drivers, race_meta, lap)
    by_driver: dict[str, list[dict]] = {}
    timed = laps[laps["stint"].notna()].sort_values(["driver", "lap"], kind="stable")
    for (code, stint), g in timed.groupby(["driver", "stint"], sort=True):
        first = g.iloc[0]
        by_driver.setdefault(code, []).append(
            {
                "stint": int(stint),
                "compound": to_json_value(first["compound"]),
                "start_lap": int(first["lap"]),
                "end_lap": int(g["lap"].iloc[-1]),
                "start_tyre_age": to_json_value(first["tyre_life"]),
            }
        )
    return {
        "race_id": race_meta["race_id"],
        "lap": lap,
        "drivers": [{"code": d["code"], "stints": by_driver.get(d["code"], [])} for d in state["drivers"]],
    }


def _fit(xs: list[float], ys: list[float]) -> dict | None:
    """Least-squares line y = intercept + slope * x; null below the minimum or with one x value."""
    n = len(xs)
    if n < DEG_FIT_MIN_POINTS:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return {"slope_s_per_lap": _r(slope), "intercept_s": _r(my - slope * mx), "n": n}


def degradation_points(laps: pd.DataFrame, total_laps: int, race_id: str, lap: int) -> dict:
    """Fuel-corrected clean laps by tyre age per dry compound, each with a fitted line."""
    laps = laps[laps["lap"] <= lap]
    clean = laps[clean_mask(laps) & laps["tyre_life"].notna()].sort_values(["driver", "lap"], kind="stable")
    fc = fuel_corrected(clean["lap_time_s"].astype(float), clean["lap"], total_laps)
    compounds = []
    for compound in config.DRY_COMPOUNDS:
        sel = clean["compound"] == compound
        if not sel.any():
            continue
        points = [
            {"code": code, "lap": int(n), "tyre_age": int(age), "fuel_corrected_s": _r(t)}
            for code, n, age, t in zip(clean.loc[sel, "driver"], clean.loc[sel, "lap"],
                                       clean.loc[sel, "tyre_life"], fc[sel])
        ]
        fit = _fit([float(p["tyre_age"]) for p in points], [float(t) for t in fc[sel]])
        compounds.append({"compound": compound, "fit": fit, "points": points})
    return {"race_id": race_id, "lap": lap, "compounds": compounds}
