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


# Reliability bins of the model's p_podium: [0, 0.2), ..., [0.8, 1.0].
RELIABILITY_EDGES: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
LOG_LOSS_CLIP = 0.001


def log_loss(forecasts: Iterable[float], outcomes: Iterable[int]) -> float | None:
    """Mean -(o ln p + (1 - o) ln(1 - p)), p clipped to [0.001, 0.999], rounded to 4 decimals."""
    terms = []
    for p, o in zip(forecasts, outcomes, strict=True):
        p = min(1.0 - LOG_LOSS_CLIP, max(LOG_LOSS_CLIP, float(p)))
        terms.append(-(o * math.log(p) + (1 - o) * math.log(1.0 - p)))
    return round(sum(terms) / len(terms), 4) if terms else None


def reliability(pairs: list[Pair]) -> list[dict]:
    """Five bins of the model forecast with count, mean forecast and observed podium rate."""
    bins = []
    last = len(RELIABILITY_EDGES) - 2
    for i, (lo, hi) in enumerate(zip(RELIABILITY_EDGES[:-1], RELIABILITY_EDGES[1:], strict=True)):
        inside = [(m, o) for m, _, o in pairs if lo <= m < hi or (i == last and m == hi)]
        n = len(inside)
        bins.append(
            {
                "bin_low": lo,
                "bin_high": hi,
                "count": n,
                "mean_forecast": round(sum(m for m, _ in inside) / n, 4) if n else None,
                "observed_rate": round(sum(o for _, o in inside) / n, 4) if n else None,
            }
        )
    return bins


def podium_calibration(pairs: list[Pair]) -> dict:
    """``log_loss_model``, ``log_loss_baseline`` and ``reliability`` over the podium pairs."""
    outcomes = [o for _, _, o in pairs]
    return {
        "log_loss_model": log_loss([m for m, _, _ in pairs], outcomes),
        "log_loss_baseline": log_loss([b for _, b, _ in pairs], outcomes),
        "reliability": reliability(pairs),
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
    pairs = [p for r in races for p in r.pairs]
    return {
        **podium_skill(pairs),
        **podium_calibration(pairs),
        **lap_scores([e for r in races for e in r.err_model], [e for r in races for e in r.err_baseline]),
        "hit_rate": hit_rate(e for r in races for e in r.events),
    }


def race_inputs(
    data_dir: Path,
    race_id: str,
    model_name: str,
    *,
    model=None,
    orders: Mapping[int, Mapping[str, int]] | None = None,
) -> RaceInputs:
    """Read one analyzed race for one model: checkpoint pairs, lap errors, events with outcomes.

    ``model`` is an already loaded model (default: load ``model_name`` from disk);
    ``orders`` are running orders already computed by the caller (``{lap: {code:
    position}}``); any checkpoint or final lap missing from them is computed here.
    """
    # Imported here: the loaders pull in the feature pipeline, which the pure scorers don't need.
    from augur.models import registry
    from augur.replay import ReplayStore
    from augur.state import positions_by_lap
    from augur.train import race_table

    store = ReplayStore(data_dir)
    race = store.get_race(race_id)
    if race is None:
        raise ValueError(f"missing race {race_id}, run augur.ingest first")
    total = int(race["total_laps"])
    cps = checkpoints(total)
    order: dict[int, Mapping[str, int]] = dict(orders or {})
    missing = [n for n in (*cps, total) if n not in order]
    if missing:
        laps = store.laps_until(race_id, total)
        meta = {"race_id": race_id, "total_laps": total}
        order.update(positions_by_lap(laps, store.list_drivers(race_id), meta, missing))

    p_podium_at: dict[int, dict[str, float]] = {}
    for row in store.positions_until(race_id, model_name, total):
        p_podium_at.setdefault(row["lap"], {})[row["code"]] = row["p_podium"]
    pairs = podium_pairs(
        {c: order[c] for c in cps},
        p_podium_at,
        [code for code, position in order[total].items() if position <= PODIUM],
    )

    if model is None:
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
