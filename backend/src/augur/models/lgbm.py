"""Built-in LightGBM lap-time model with fixed, deterministic parameters."""

from __future__ import annotations

import lightgbm as lgb
import pandas as pd

from augur import config
from augur.features import FEATURE_COLUMNS
from augur.models.base import JoblibModel

PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_child_samples": 20,
    "random_state": 42,
    "deterministic": True,
    "force_row_wise": True,
    "n_jobs": 1,
    "verbose": -1,
}


class LightGBMModel(JoblibModel):
    name = "lightgbm"
    author = "AUGUR"

    @staticmethod
    def _matrix(features: pd.DataFrame) -> pd.DataFrame:
        x = features[list(FEATURE_COLUMNS)].copy()
        x["compound"] = pd.Categorical(x["compound"], categories=list(config.DRY_COMPOUNDS))
        for col in FEATURE_COLUMNS:
            if col != "compound":
                x[col] = pd.to_numeric(x[col], errors="coerce").astype(float)
        return x

    def fit(self, features: pd.DataFrame, target: pd.Series) -> None:
        self.model_ = lgb.LGBMRegressor(**PARAMS)
        self.model_.fit(self._matrix(features), pd.Series(target, dtype=float).to_numpy())

    def predict(self, features: pd.DataFrame) -> pd.Series:
        if features.empty:
            return pd.Series(dtype=float, index=features.index)
        return pd.Series(self.model_.predict(self._matrix(features)), index=features.index, dtype=float)
