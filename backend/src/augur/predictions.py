"""Next-lap predictions at a replay lap."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd

from augur.features import FEATURE_COLUMNS, build_feature_table
from augur.models.base import LapTimeModel
from augur.models.degradation import current_stint_degradation


def predict_lap_times(table: pd.DataFrame, model: LapTimeModel) -> pd.Series:
    """Predicted lap time (recent pace + model delta) per feature row; NaN without recent pace."""
    out = pd.Series(np.nan, index=table.index, dtype=float)
    ok = table["recent_pace_s"].notna()
    if ok.any():
        rows = table.loc[ok]
        delta = np.asarray(model.predict(rows[list(FEATURE_COLUMNS)]), dtype=float)
        if delta.shape != (len(rows),):
            raise ValueError(f"model {model.name} returned {delta.shape} predictions for {len(rows)} rows")
        out.loc[ok] = rows["recent_pace_s"].to_numpy() + delta
    return out


def _r(value, digits: int = 3):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)


def predictions_at(
    laps: pd.DataFrame,
    total_laps: int,
    lap: int,
    model: LapTimeModel,
    prior: Mapping[str, float] | None = None,
    driver_codes: Iterable[str] = (),
) -> list[dict]:
    """Per driver: prediction for lap ``lap + 1`` from laps up to ``lap`` only."""
    laps = laps[laps["lap"] <= lap]
    table = build_feature_table(laps, total_laps, prior)
    table = table[table["target_lap"] == lap + 1].reset_index(drop=True)
    predicted = predict_lap_times(table, model)
    deg = current_stint_degradation(laps, total_laps)
    by_driver = {d: i for i, d in enumerate(table["driver"])}

    out = []
    for code in sorted(set(driver_codes) | set(table["driver"])):
        i = by_driver.get(code)
        recent = None if i is None else _r(table.at[i, "recent_pace_s"])
        if recent is None:  # fewer than 3 clean laps
            out.append(
                {"code": code, "predicted_next_lap_s": None, "recent_pace_s": None,
                 "deg_s_per_lap": None, "deg_laps": None, "cliff": None}
            )
            continue
        d = deg.get(code, {})
        out.append(
            {
                "code": code,
                "predicted_next_lap_s": _r(predicted.iat[i]),
                "recent_pace_s": recent,
                "deg_s_per_lap": d.get("deg_s_per_lap"),
                "deg_laps": d.get("deg_laps"),
                "cliff": d.get("cliff"),
            }
        )
    return out
