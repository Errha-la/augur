"""Train and evaluate a lap-time model.

Usage:
    python -m augur.train [--model lightgbm] [--train 2024:2-11] [--test 2024:1,24] [--data-dir DIR]

Writes data/models/<model>.joblib and data/models/<model>_metrics.json.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from augur import catalog, config
from augur.features import build_feature_table, training_rows
from augur.models import registry
from augur.priors import circuit_priors
from augur.replay import ReplayStore

DEFAULT_TRAIN = "2024:2-11"
DEFAULT_TEST = "2024:1,24"
MAX_ROUND = 99


def parse_races(text: str) -> list[tuple[int, int]]:
    """``<year>:<rounds>`` with rounds like ``2-11`` or ``1,24`` -> [(year, round), ...]."""
    try:
        year_text, rounds_text = text.split(":", 1)
        year = int(year_text, 10)
        rounds: list[int] = []
        for part in rounds_text.split(","):
            if "-" in part:
                lo, hi = (int(p, 10) for p in part.split("-", 1))
                if lo > hi:
                    raise ValueError
                rounds.extend(range(lo, hi + 1))
            else:
                rounds.append(int(part, 10))
    except ValueError:
        raise ValueError(f"invalid race list {text!r}, expected <year>:<rounds> such as 2024:2-11") from None
    if not 1950 <= year <= 2100 or any(not 1 <= r <= MAX_ROUND for r in rounds):
        raise ValueError(f"invalid race list {text!r}: year or round out of range")
    return [(year, r) for r in dict.fromkeys(rounds)]


def _race_arg(text: str) -> list[tuple[int, int]]:
    try:
        return parse_races(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m augur.train", description="Train and evaluate a lap-time model.")
    p.add_argument("--model", default=config.DEFAULT_MODEL)
    p.add_argument("--train", type=_race_arg, default=parse_races(DEFAULT_TRAIN))
    p.add_argument("--test", type=_race_arg, default=parse_races(DEFAULT_TEST))
    p.add_argument("--data-dir", type=Path, default=None, help="data root (default: repo data/)")
    return p


class TrainError(Exception):
    pass


def race_table(store: ReplayStore, race_id: str) -> tuple[pd.DataFrame, pd.Series]:
    total = int(store.get_race(race_id)["total_laps"])
    table = build_feature_table(store.laps_until(race_id, total), total, circuit_priors(store, race_id))
    return training_rows(table)


def _stack(store: ReplayStore, race_ids: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    parts = [race_table(store, r) for r in race_ids]
    return (
        pd.concat([p[0] for p in parts], ignore_index=True),
        pd.concat([p[1] for p in parts], ignore_index=True),
    )


def train(model_name: str, train_races, test_races, data_dir: Path) -> dict:
    cls = registry.get_model_class(model_name)  # UnknownModelError
    store = ReplayStore(data_dir)

    def label(year: int, rnd: int) -> str:
        return store.race_id_for(year, rnd) or f"{year}-{rnd:02d}"

    overlap = [p for p in train_races if p in set(test_races)]
    if overlap:
        raise TrainError(f"train and test races overlap: {', '.join(label(*p) for p in overlap)}")
    for year, rnd in [*train_races, *test_races]:
        if store.race_id_for(year, rnd) is None:
            raise TrainError(f"missing race {label(year, rnd)}, run augur.ingest first")

    train_ids = [label(*p) for p in train_races]
    test_ids = [label(*p) for p in test_races]
    x_train, y_train = _stack(store, train_ids)
    x_test, y_test = _stack(store, test_ids)
    if x_train.empty or x_test.empty:
        raise TrainError("no clean laps with known recent pace in the train or test races")

    model = cls()
    model.fit(x_train, y_train)
    predicted = np.asarray(model.predict(x_test), dtype=float)
    if predicted.shape != (len(x_test),) or not np.isfinite(predicted).all():
        raise TrainError(f"model {model_name} returned {predicted.shape} predictions or non-finite values")

    metrics = {
        "model": cls.name,
        "author": cls.author,
        "train_races": train_ids,
        "test_races": test_ids,
        "n_train": int(len(x_train)),
        "n_test": int(len(x_test)),
        "mae_model_s": round(float(np.mean(np.abs(y_test.to_numpy() - predicted))), 4),
        "mae_baseline_s": round(float(np.mean(np.abs(y_test.to_numpy()))), 4),
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    out = registry.models_dir(data_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.save(registry.model_path(data_dir, model_name))
    registry.metrics_path(data_dir, model_name).write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir: Path = args.data_dir if args.data_dir is not None else catalog.default_data_dir()
    try:
        m = train(args.model, args.train, args.test, data_dir)
    except (registry.UnknownModelError, TrainError) as exc:
        print(str(exc), flush=True)
        return 1
    print(
        f"{m['model']}: mae_model_s={m['mae_model_s']:.4f} mae_baseline_s={m['mae_baseline_s']:.4f}"
        f" (n_train={m['n_train']}, n_test={m['n_test']})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
