"""Naive baseline: the next lap equals recent pace (delta 0)."""

from __future__ import annotations

import pandas as pd

from augur.models.base import JoblibModel


class BaselineModel(JoblibModel):
    name = "baseline"
    author = "AUGUR"

    def fit(self, features: pd.DataFrame, target: pd.Series) -> None:
        self.n_train_ = int(len(target))

    def predict(self, features: pd.DataFrame) -> pd.Series:
        return pd.Series(0.0, index=features.index, dtype=float)
