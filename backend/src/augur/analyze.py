"""Precompute race events lap by lap into SQLite.

Usage:
    python -m augur.analyze --race <race_id> [--model lightgbm] [--data-dir DIR]

Steps an EventEngine over a ReplayFeed from lap 1 to total_laps and replaces
the race's rows for that model in the ``events`` table.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from augur import catalog, config
from augur.events.engine import EventEngine
from augur.feed import ReplayFeed
from augur.models import registry
from augur.priors import circuit_priors
from augur.replay import RaceNotFound, ReplayStore


class AnalyzeError(Exception):
    pass


def compute_events(data_dir: Path, race_id: str, model_name: str) -> list[dict]:
    store = ReplayStore(data_dir)
    if store.get_race(race_id) is None:
        raise AnalyzeError(f"race not found: {race_id}")
    try:
        model = registry.load_trained(data_dir, model_name)
        metrics = registry.read_metrics(data_dir, model_name)
    except (registry.UnknownModelError, registry.ModelNotTrainedError) as exc:
        raise AnalyzeError(str(exc)) from None
    if race_id in metrics.get("train_races", []):
        raise AnalyzeError(f"race {race_id} is in the training set of model {model_name}")
    feed = ReplayFeed(race_id, store)
    engine = EventEngine(feed, model, circuit_priors(store, race_id))
    return [e for lap in range(1, feed.total_laps + 1) for e in engine.step(lap)]


def replace_events(data_dir: Path, race_id: str, model_name: str, events: list[dict]) -> None:
    """Replace the race's events for the model in one transaction."""
    conn = catalog.connect(data_dir)
    try:
        with conn:
            conn.execute("DELETE FROM events WHERE race_id = ? AND model = ?", (race_id, model_name))
            conn.executemany(
                "INSERT INTO events (race_id, model, id, lap, type, drivers, severity, title,"
                " analysis, evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        race_id, model_name, e["id"], e["lap"], e["type"], json.dumps(e["drivers"]),
                        e["severity"], e["title"], json.dumps(e["analysis"]),
                        json.dumps(e["evidence"], sort_keys=True),
                    )
                    for e in events
                ],
            )
            conn.execute(
                "INSERT OR REPLACE INTO analyses (race_id, model, n_events, analyzed_at) VALUES (?, ?, ?, ?)",
                (race_id, model_name, len(events), datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
    finally:
        conn.close()


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m augur.analyze", description="Precompute race events.")
    p.add_argument("--race", required=True)
    p.add_argument("--model", default=config.DEFAULT_MODEL)
    p.add_argument("--data-dir", type=Path, default=None, help="data root (default: repo data/)")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir: Path = args.data_dir if args.data_dir is not None else catalog.default_data_dir()
    try:
        events = compute_events(data_dir, args.race, args.model)
    except (AnalyzeError, RaceNotFound) as exc:
        print(str(exc), flush=True)
        return 1
    replace_events(data_dir, args.race, args.model, events)
    print(f"analyzed {args.race}: {len(events)} events", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
