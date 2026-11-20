"""End-of-race Wrapped content: summary, podium call, scores, highlights, one driver.

Only built at the final lap (the API refuses earlier laps), so it may read the
whole race. Scores come from ``augur.scoring`` exactly as ``augur.bench``
computes them for one race.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

from augur.models import registry
from augur.replay import ReplayStore
from augur.scoring import PODIUM, checkpoints, race_inputs, scores
from augur.state import race_state

SCORE_KEYS = (
    "position_skill_pct", "brier_model", "brier_baseline", "lap_improvement_pct", "mae_model_s", "mae_baseline_s",
)


def _top(events: Iterable[Mapping], outcome: str | None = None) -> dict | None:
    """Highest severity (ties: earliest lap) among events, optionally with one outcome."""
    pool = [e for e in events if outcome is None or e.get("outcome") == outcome]
    if not pool:
        return None
    return dict(min(pool, key=lambda e: (-e["severity"], e["lap"], e["id"])))


def pick_highlights(events: list[Mapping]) -> dict:
    return {
        "best_call": _top(events, "hit"),
        "biggest_miss": _top(events, "miss"),
        "biggest_moment": _top(events),
    }


def podium_call(lap: int, p_podium: Mapping[str, float | None], final_podium: list[str]) -> dict:
    """The three highest ``p_podium`` at ``lap`` against the actual podium."""
    ranked = sorted(p_podium.items(), key=lambda kv: (-(kv[1] or 0.0), kv[0]))[:PODIUM]
    predicted = [{"code": code, "p_podium": p} for code, p in ranked]
    return {
        "lap": lap,
        "predicted": predicted,
        "actual": list(final_podium),
        "correct": sum(1 for p in predicted if p["code"] in set(final_podium)),
    }


def _stints(laps, code: str) -> list[dict]:
    rows = laps[laps["driver"] == code].sort_values("lap")
    stints: list[dict] = []
    previous = object()
    for stint, compound in zip(rows["stint"], rows["compound"]):
        key = None if stint is None or stint != stint else int(stint)  # NaN-safe
        if stints and key == previous:
            stints[-1]["laps"] += 1
        else:
            stints.append({"compound": compound if isinstance(compound, str) else None, "laps": 1})
        previous = key
    return stints


def build(data_dir: Path, race_id: str, model_name: str, driver: str) -> dict:
    store = ReplayStore(data_dir)
    race = store.get_race(race_id)
    total = int(race["total_laps"])
    laps = store.laps_until(race_id, total)
    drivers = store.list_drivers(race_id)
    meta = {"race_id": race_id, "total_laps": total}

    order_by_lap: dict[int, dict[str, int]] = {}
    for n in range(1, total + 1):
        state = race_state(laps[laps["lap"] <= n], drivers, meta, n)
        order_by_lap[n] = {d["code"]: d["position"] for d in state["drivers"]}
    final = order_by_lap[total]
    final_podium = [code for code, _ in sorted(final.items(), key=lambda kv: kv[1])][:PODIUM]

    p_podium_by_lap: dict[int, dict[str, float]] = {}
    for row in store.positions_until(race_id, model_name, total):
        p_podium_by_lap.setdefault(row["lap"], {})[row["code"]] = row["p_podium"]

    events = sorted(store.events_until(race_id, model_name, total), key=lambda e: (e["lap"], -e["severity"], e["id"]))
    result = scores([race_inputs(data_dir, race_id, model_name)])
    cls = registry.get_model_class(model_name)
    try:
        author = registry.read_metrics(data_dir, model_name).get("author") or cls.author
    except registry.ModelNotTrainedError:
        author = cls.author

    info = next(d for d in drivers if d["code"] == driver)
    middle = checkpoints(total)[1]
    return {
        "race_id": race_id,
        "event_name": race["event_name"],
        "year": race["year"],
        "model": {"name": model_name, "author": author},
        "summary": {
            "winner": final_podium[0] if final_podium else None,
            "podium": final_podium,
            "total_laps": total,
            "n_events": len(events),
            "n_events_by_type": dict(sorted(Counter(e["type"] for e in events).items())),
        },
        "podium_call": podium_call(middle, p_podium_by_lap.get(middle, {}), final_podium),
        "score": {k: result[k] for k in SCORE_KEYS},
        "hit_rate": result["hit_rate"],
        **pick_highlights(events),
        "driver": {
            "code": driver,
            "team": info["team"],
            "team_color": info["team_color"],
            "grid_position": info["grid_position"],
            "final_position": final.get(driver),
            "positions_by_lap": [{"lap": n, "position": order_by_lap[n].get(driver)} for n in range(1, total + 1)],
            "p_podium_by_lap": [
                {"lap": n, "p_podium": p_podium_by_lap.get(n, {}).get(driver)} for n in range(1, total + 1)
            ],
            "stints": _stints(laps, driver),
            "events": [e for e in events if driver in e["drivers"]],
        },
    }
