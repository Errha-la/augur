"""Race state at a lap, computed only from the laps it is given."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd


def to_json_value(value: Any) -> Any:
    """Convert numpy/pandas scalars to plain Python; NaN/NA/NaT -> None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def race_state(
    laps: pd.DataFrame,
    drivers: Iterable[Mapping[str, Any]],
    race_meta: Mapping[str, Any],
    lap: int,
) -> dict:
    """State of the race after lap ``lap``.

    ``laps`` must contain only rows with ``lap <= lap`` (rows beyond are
    ignored defensively). ``drivers`` are catalog rows (code, team, team_color).
    Drivers listed in the catalog without any completed lap are ranked last
    with ``laps_completed`` 0 and null lap fields.
    """
    laps = laps[laps["lap"] <= lap]
    catalog = {d["code"]: d for d in drivers}

    # Last completed lap per driver.
    last = (
        laps.sort_values(["driver", "lap"])
        .groupby("driver", sort=False)
        .tail(1)
        .set_index("driver")
    )
    session_at = {
        (d, int(n)): to_json_value(t)
        for d, n, t in zip(laps["driver"], laps["lap"], laps["session_time_s"])
    }

    entries = []
    for code in sorted(set(catalog) | set(last.index)):
        info = catalog.get(code, {})
        if code in last.index:
            row = last.loc[code]
            completed = int(row["lap"])
            stint = to_json_value(row["stint"])
            entries.append(
                {
                    "code": code,
                    "team": to_json_value(row["team"]) or info.get("team"),
                    "team_color": info.get("team_color"),
                    "laps_completed": completed,
                    "last_lap_time_s": to_json_value(row["lap_time_s"]),
                    "compound": to_json_value(row["compound"]),
                    "tyre_age_laps": to_json_value(row["tyre_life"]),
                    "stint": stint,
                    "pit_count": None if stint is None else int(stint) - 1,
                    "_session": to_json_value(row["session_time_s"]),
                    "_track_status": to_json_value(row["track_status"]),
                }
            )
        else:
            entries.append(
                {
                    "code": code,
                    "team": info.get("team"),
                    "team_color": info.get("team_color"),
                    "laps_completed": 0,
                    "last_lap_time_s": None,
                    "compound": None,
                    "tyre_age_laps": None,
                    "stint": None,
                    "pit_count": None,
                    "_session": None,
                    "_track_status": None,
                }
            )

    entries.sort(
        key=lambda e: (
            -e["laps_completed"],
            e["_session"] is None,
            e["_session"] if e["_session"] is not None else 0.0,
            e["code"],
        )
    )

    leader = entries[0] if entries and entries[0]["laps_completed"] > 0 else None
    out_drivers = []
    for position, e in enumerate(entries, start=1):
        gap = None
        behind = None
        if leader is not None:
            behind = leader["laps_completed"] - e["laps_completed"]
            if e["laps_completed"] > 0 and e["_session"] is not None:
                leader_t = session_at.get((leader["code"], e["laps_completed"]))
                if leader_t is not None:
                    gap = round(e["_session"] - leader_t, 3)
        out_drivers.append(
            {
                "code": e["code"],
                "team": e["team"],
                "team_color": e["team_color"],
                "position": position,
                "laps_completed": e["laps_completed"],
                "last_lap_time_s": e["last_lap_time_s"],
                "compound": e["compound"],
                "tyre_age_laps": e["tyre_age_laps"],
                "stint": e["stint"],
                "pit_count": e["pit_count"],
                "gap_to_leader_s": gap,
                "laps_behind_leader": behind,
            }
        )

    return {
        "race_id": race_meta["race_id"],
        "lap": lap,
        "total_laps": race_meta["total_laps"],
        "track_status": leader["_track_status"] if leader else None,
        "drivers": out_drivers,
    }


def positions_by_lap(
    laps: pd.DataFrame,
    drivers: Iterable[Mapping[str, Any]],
    race_meta: Mapping[str, Any],
    at_laps: Iterable[int],
) -> dict[int, dict[str, int]]:
    """``{lap: {code: position}}`` after each lap in ``at_laps``, ranked as ``race_state`` ranks.

    The one place outcomes, scoring and the Wrapped read the running order, so
    they always agree on who was where (for example, how a retired driver ranks).
    """
    drivers = list(drivers)
    out: dict[int, dict[str, int]] = {}
    for lap in sorted({int(n) for n in at_laps}):
        state = race_state(laps[laps["lap"] <= lap], drivers, race_meta, lap)
        out[lap] = {d["code"]: d["position"] for d in state["drivers"]}
    return out
