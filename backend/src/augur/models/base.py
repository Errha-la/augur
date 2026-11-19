"""The LapTimeModel protocol and shared save/load helpers.

A model predicts the *delta* between a driver's next clean lap time and
their recent pace (median of the last 3 clean laps), from the columns in
``augur.features.FEATURE_COLUMNS``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import joblib
import pandas as pd


@runtime_checkable
class LapTimeModel(Protocol):
    name: str
    author: str

    def fit(self, features: pd.DataFrame, target: pd.Series) -> None: ...

    def predict(self, features: pd.DataFrame) -> pd.Series: ...

    def save(self, path: str | Path) -> None: ...

    @classmethod
    def load(cls, path: str | Path) -> "LapTimeModel": ...


class JoblibModel:
    """save/load through joblib.

    joblib files are pickles: loading one runs code from the file, so AUGUR
    only loads files it wrote itself under ``data/models/``. ``load`` also
    refuses an object of another class.
    """

    def save(self, path: str | Path) -> None:
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | Path):
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(f"{path} holds a {type(obj).__name__}, expected {cls.__name__}")
        return obj
