"""Precompute race events and position predictions lap by lap into SQLite.

Usage:
    python -m augur.analyze --race <race_id> [--model lightgbm] [--runs 1000] [--data-dir DIR]

Steps an EventEngine over a ReplayFeed from lap 1 to total_laps, runs the
position simulator at every lap, and replaces the race's rows for that model
in the ``events`` and ``position_predictions`` tables.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from augur import catalog, config
from augur.events.engine import EventEngine
from augur.events.outcomes import resolve_outcomes
from augur.feed import ReplayFeed
from augur.models import registry
from augur.positions import positions_at
from augur.priors import circuit_priors
from augur.replay import RaceNotFound, ReplayStore


class AnalyzeError(Exception):
    pass


def compute_analysis(
    data_dir: Path,
    race_id: str,
    model_name: str,
    runs: int = config.POSITION_RUNS_DEFAULT,
    seed: int = config.POSITION_SEED_DEFAULT,
) -> tuple[list[dict], dict[int, list[dict]]]:
    """(events, {lap: position predictions}) for every lap of the race."""
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
    prior = circuit_priors(store, race_id)
    engine = EventEngine(feed, model, prior)
    events: list[dict] = []
    positions: dict[int, list[dict]] = {}
    for lap in range(1, feed.total_laps + 1):
        events += engine.step(lap)
        positions[lap] = positions_at(feed, lap, model, prior, runs=runs, seed=seed)
    # Outcomes look past each event by design; the API hides them until outcome_lap.
    meta = {"race_id": race_id, "total_laps": feed.total_laps}
    events = resolve_outcomes(events, feed.laps_until(feed.total_laps), store.list_drivers(race_id), meta)
    return events, positions


def _write_events(conn, race_id: str, model_name: str, events: list[dict]) -> None:
    rows = [
        (
            race_id, model_name, e["id"], e["lap"], e["type"], json.dumps(e["drivers"]),
            e["severity"], e["title"], json.dumps(e["analysis"]),
            json.dumps(e["evidence"], sort_keys=True),
            e.get("outcome"), e.get("outcome_lap"), e.get("outcome_text"),
        )
        for e in events
    ]
    # Commentary was grounded in the old analysis and evidence (event ids stay the same
    # across re-analysis): drop it for events that changed or are gone, keep the rest.
    new = {r[2]: (r[8], r[9]) for r in rows}
    old = conn.execute(
        "SELECT id, analysis, evidence FROM events WHERE race_id = ? AND model = ?", (race_id, model_name)
    ).fetchall()
    conn.executemany(
        "DELETE FROM commentary WHERE event_id = ? AND model = ?",
        [(r[0], model_name) for r in old if new.get(r[0]) != (r[1], r[2])],
    )
    conn.execute("DELETE FROM events WHERE race_id = ? AND model = ?", (race_id, model_name))
    conn.executemany(
        "INSERT INTO events (race_id, model, id, lap, type, drivers, severity, title,"
        " analysis, evidence, outcome, outcome_lap, outcome_text)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.execute(
        "INSERT OR REPLACE INTO analyses (race_id, model, n_events, analyzed_at) VALUES (?, ?, ?, ?)",
        (race_id, model_name, len(events), datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )


def _write_positions(
    conn, race_id: str, model_name: str, positions: dict[int, list[dict]], runs: int, seed: int
) -> None:
    conn.execute("DELETE FROM position_predictions WHERE race_id = ? AND model = ?", (race_id, model_name))
    conn.executemany(
        "INSERT INTO position_predictions (race_id, model, lap, code, p_win, p_podium, p_points,"
        " expected_position, position_p10, position_p90, runs, seed, position_distribution)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                race_id, model_name, lap, d["code"], d["p_win"], d["p_podium"], d["p_points"],
                d["expected_position"], d["position_p10"], d["position_p90"], runs, seed,
                json.dumps(d["position_distribution"]) if d.get("position_distribution") is not None else None,
            )
            for lap, drivers in sorted(positions.items())
            for d in drivers
        ],
    )


def _transaction(data_dir: Path, *writes) -> None:
    conn = catalog.connect(data_dir)
    try:
        with conn:  # one transaction; rolls back on exception
            for write in writes:
                write(conn)
    finally:
        conn.close()


def replace_events(data_dir: Path, race_id: str, model_name: str, events: list[dict]) -> None:
    """Replace the race's events for the model in one transaction."""
    _transaction(data_dir, lambda c: _write_events(c, race_id, model_name, events))


def replace_positions(
    data_dir: Path, race_id: str, model_name: str, positions: dict[int, list[dict]], runs: int, seed: int
) -> None:
    """Replace the race's position predictions for the model in one transaction."""
    _transaction(data_dir, lambda c: _write_positions(c, race_id, model_name, positions, runs, seed))


def store_analysis(
    data_dir: Path, race_id: str, model_name: str, events: list[dict], positions: dict[int, list[dict]],
    runs: int, seed: int,
) -> None:
    """Replace the race's events and position predictions together, so no reader (the API's
    Wrapped cache, keyed by ``analyzed_at``) sees new events with old positions."""
    _transaction(
        data_dir,
        lambda c: _write_events(c, race_id, model_name, events),
        lambda c: _write_positions(c, race_id, model_name, positions, runs, seed),
    )


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m augur.analyze", description="Precompute race events and position predictions."
    )
    p.add_argument("--race", required=True)
    p.add_argument("--model", default=config.DEFAULT_MODEL)
    p.add_argument(
        "--runs",
        type=int,
        default=config.POSITION_RUNS_DEFAULT,
        help=f"position simulation runs per lap ({config.POSITION_RUNS_MIN}..{config.POSITION_RUNS_MAX})",
    )
    p.add_argument("--data-dir", type=Path, default=None, help="data root (default: repo data/)")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir: Path = args.data_dir if args.data_dir is not None else catalog.default_data_dir()
    if not config.POSITION_RUNS_MIN <= args.runs <= config.POSITION_RUNS_MAX:
        print(f"runs must be {config.POSITION_RUNS_MIN}..{config.POSITION_RUNS_MAX}", flush=True)
        return 1
    seed = config.POSITION_SEED_DEFAULT
    started = time.perf_counter()
    try:
        events, positions = compute_analysis(data_dir, args.race, args.model, runs=args.runs, seed=seed)
    except (AnalyzeError, RaceNotFound) as exc:
        print(str(exc), flush=True)
        return 1
    store_analysis(data_dir, args.race, args.model, events, positions, args.runs, seed)
    elapsed = time.perf_counter() - started
    print(f"position predictions: {len(positions)} laps, {args.runs} runs per lap, {elapsed:.1f} s", flush=True)
    print(f"analyzed {args.race}: {len(events)} events", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
