"""Scores shared by ``augur.bench`` and the Wrapped endpoint.

Headline: podium skill — Brier score of the model's ``p_podium`` against a
"current order holds" baseline at three checkpoints. The pure functions here
take plain data so the bench and the API compute identical numbers.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# (model forecast, baseline forecast, outcome) for one (checkpoint, driver) pair.
Pair = tuple[float, float, int]

PODIUM = 3


def checkpoints(total_laps: int) -> list[int]:
    """Laps floor(25%), floor(50%) and floor(75%) of the race (at least lap 1)."""
    return [max(1, math.floor(total_laps * f)) for f in (0.25, 0.5, 0.75)]


def podium_pairs(
    order_at: Mapping[int, Mapping[str, int]],
    p_podium_at: Mapping[int, Mapping[str, float | None]],
    final_podium: Iterable[str],
) -> list[Pair]:
    """One pair per checkpoint c and driver d in the order at c.

    ``order_at[c]`` maps driver code to position at c; ``p_podium_at[c]`` the
    model's ``p_podium`` (a driver without a forecast counts as 0).
    """
    podium = set(final_podium)
    pairs: list[Pair] = []
    for c in sorted(order_at):
        forecasts = p_podium_at.get(c, {})
        for code, position in sorted(order_at[c].items()):
            model = forecasts.get(code)
            pairs.append((float(model or 0.0), 1.0 if position <= PODIUM else 0.0, int(code in podium)))
    return pairs


def podium_skill(pairs: list[Pair]) -> dict:
    """``brier_model``, ``brier_baseline`` (mean squared errors) and ``position_skill_pct``.

    The skill is ``100 × (1 − brier_model / brier_baseline)`` rounded to 1
    decimal, or None when ``brier_baseline`` is 0 (the order never changed) or
    there are no pairs.
    """
    if not pairs:
        return {"brier_model": None, "brier_baseline": None, "position_skill_pct": None}
    n = len(pairs)
    brier_model = sum((m - o) ** 2 for m, _, o in pairs) / n
    brier_baseline = sum((b - o) ** 2 for _, b, o in pairs) / n
    # "+ 0.0" turns a rounded -0.0 into 0.0, so a tie never prints as "-0.0%".
    skill = None if brier_baseline == 0 else round(100.0 * (1.0 - brier_model / brier_baseline), 1) + 0.0
    return {
        "brier_model": round(brier_model, 4),
        "brier_baseline": round(brier_baseline, 4),
        "position_skill_pct": skill,
    }


# -- lap times and event calls ------------------------------------------------------


def lap_scores(err_model: Iterable[float], err_baseline: Iterable[float]) -> dict:
    """Mean absolute lap-time errors of the model and the baseline over the same laps.

    ``lap_improvement_pct`` is ``100 × (mae_baseline − mae_model) / mae_baseline``
    rounded to 1 decimal (positive: the model beats the baseline).
    """
    em, eb = list(err_model), list(err_baseline)
    if not em or len(em) != len(eb):
        return {"lap_improvement_pct": None, "mae_model_s": None, "mae_baseline_s": None}
    mae_model = sum(em) / len(em)
    mae_baseline = sum(eb) / len(eb)
    improvement = None if mae_baseline == 0 else round(100.0 * (mae_baseline - mae_model) / mae_baseline, 1) + 0.0
    return {
        "lap_improvement_pct": improvement,
        "mae_model_s": round(mae_model, 4),
        "mae_baseline_s": round(mae_baseline, 4),
    }


def hit_rate(events: Iterable[Mapping]) -> dict:
    """Hits over resolved calls (hits + misses) per type and overall; voids are excluded."""
    counts = {"undercut": {"hits": 0, "resolved": 0}, "degradation": {"hits": 0, "resolved": 0}}
    kinds = {"undercut_window": "undercut", "degradation_warning": "degradation"}
    for e in events:
        kind = kinds.get(e.get("type"))
        if kind is None or e.get("outcome") not in ("hit", "miss"):
            continue
        counts[kind]["resolved"] += 1
        counts[kind]["hits"] += e["outcome"] == "hit"
    hits = sum(c["hits"] for c in counts.values())
    resolved = sum(c["resolved"] for c in counts.values())
    return {
        **counts,
        "hits": hits,
        "resolved": resolved,
        "overall_pct": None if resolved == 0 else round(100.0 * hits / resolved, 1),
    }


# -- one race's raw material, and the scores over one or more races ----------------


@dataclass(frozen=True)
class RaceInputs:
    race_id: str
    pairs: list[Pair]
    err_model: list[float]
    err_baseline: list[float]
    events: list[dict]


def scores(races: Iterable[RaceInputs]) -> dict:
    """Podium skill, lap-time scores and hit rate, pooled over ``races``.

    Pooling combines checkpoint pairs, clean laps and events (not averages of
    per-race scores), so one race gives that race's scores and both benchmark
    races give the pooled benchmark.
    """
    races = list(races)
    return {
        **podium_skill([p for r in races for p in r.pairs]),
        **lap_scores([e for r in races for e in r.err_model], [e for r in races for e in r.err_baseline]),
        "hit_rate": hit_rate(e for r in races for e in r.events),
    }


def race_inputs(data_dir: Path, race_id: str, model_name: str) -> RaceInputs:
    """Read one analyzed race for one model: checkpoint pairs, lap errors, events with outcomes."""
    # Imported here: the loaders pull in the feature pipeline, which the pure scorers don't need.
    from augur.models import registry
    from augur.replay import ReplayStore
    from augur.state import race_state
    from augur.train import race_table

    store = ReplayStore(data_dir)
    race = store.get_race(race_id)
    if race is None:
        raise ValueError(f"missing race {race_id}, run augur.ingest first")
    total = int(race["total_laps"])
    laps = store.laps_until(race_id, total)
    drivers = store.list_drivers(race_id)
    meta = {"race_id": race_id, "total_laps": total}

    def order(lap: int) -> dict[str, int]:
        state = race_state(laps[laps["lap"] <= lap], drivers, meta, lap)
        return {d["code"]: d["position"] for d in state["drivers"]}

    final = order(total)
    p_podium_at: dict[int, dict[str, float]] = {}
    for row in store.positions_until(race_id, model_name, total):
        p_podium_at.setdefault(row["lap"], {})[row["code"]] = row["p_podium"]
    pairs = podium_pairs(
        {c: order(c) for c in checkpoints(total)},
        p_podium_at,
        [code for code, position in final.items() if position <= PODIUM],
    )

    model = registry.load_trained(data_dir, model_name)
    x, y = race_table(store, race_id)
    if len(x):
        truth = y.to_numpy(dtype=float)
        err_model = np.abs(truth - np.asarray(model.predict(x), dtype=float)).tolist()
        err_baseline = np.abs(truth).tolist()  # the baseline predicts no change from recent pace
    else:
        err_model, err_baseline = [], []

    return RaceInputs(
        race_id=race_id,
        pairs=pairs,
        err_model=err_model,
        err_baseline=err_baseline,
        events=store.events_until(race_id, model_name, total),
    )
