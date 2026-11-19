"""Model registry: model name -> LapTimeModel class, plus trained-file lookup.

Add your own model by calling ``register(MyModel)`` below, next to the
built-in models (see docs/swap-model.md).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from augur.models.base import LapTimeModel
from augur.models.baseline import BaselineModel
from augur.models.lgbm import LightGBMModel

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

_REGISTRY: dict[str, type] = {}


class UnknownModelError(LookupError):
    def __init__(self, name: object) -> None:
        super().__init__(f"unknown model {name}")
        self.name = name

    def __str__(self) -> str:
        return self.args[0]


class ModelNotTrainedError(LookupError):
    def __init__(self, name: str) -> None:
        super().__init__(f"model {name} is not trained, run augur.train first")
        self.name = name

    def __str__(self) -> str:
        return self.args[0]


def register(cls: type) -> type:
    """Register a LapTimeModel class under ``cls.name``. Usable as a decorator."""
    name = getattr(cls, "name", None)
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ValueError(f"model name must match {NAME_RE.pattern}, got {name!r}")
    if not isinstance(getattr(cls, "author", None), str):
        raise ValueError(f"model {name} needs a str 'author'")
    for method in ("fit", "predict", "save", "load"):
        if not callable(getattr(cls, method, None)):
            raise ValueError(f"model {name} is missing method {method!r}")
    existing = _REGISTRY.get(name)
    if existing is not None and existing is not cls:
        raise ValueError(f"model name {name} is already registered")
    _REGISTRY[name] = cls
    return cls


def unregister(name: str) -> None:
    _REGISTRY.pop(name, None)


def model_names() -> list[str]:
    return sorted(_REGISTRY)


def get_model_class(name: object) -> type:
    if not isinstance(name, str) or name not in _REGISTRY:
        raise UnknownModelError(name)
    return _REGISTRY[name]


def create_model(name: str) -> LapTimeModel:
    return get_model_class(name)()


# -- trained files -------------------------------------------------------------


def models_dir(data_dir: Path | str) -> Path:
    return Path(data_dir) / "models"


def model_path(data_dir: Path | str, name: str) -> Path:
    get_model_class(name)  # only registered (path-safe) names reach the filesystem
    return models_dir(data_dir) / f"{name}.joblib"


def metrics_path(data_dir: Path | str, name: str) -> Path:
    get_model_class(name)
    return models_dir(data_dir) / f"{name}_metrics.json"


def load_trained(data_dir: Path | str, name: str) -> LapTimeModel:
    cls = get_model_class(name)
    path = model_path(data_dir, name)
    if not path.is_file():
        raise ModelNotTrainedError(name)
    return cls.load(path)


def read_metrics(data_dir: Path | str, name: str) -> dict:
    path = metrics_path(data_dir, name)
    if not path.is_file():
        raise ModelNotTrainedError(name)
    return json.loads(path.read_text(encoding="utf-8"))


# -- built-in models -----------------------------------------------------------

register(BaselineModel)
register(LightGBMModel)
