"""Score a lap-time model on the fixed benchmark races.

Usage:
    python -m augur.bench --model <name> [--data-dir DIR] [--out-dir DIR] [--runs N]

Analyzes each benchmark race with the model when it has no events, no
position predictions, or events stored before outcomes existed; then writes
``bench/<name>.json`` with pooled and per-race scores and prints one summary
line. Pooled scores pool checkpoint pairs, clean laps and events (see
``augur.scoring``), the same code the Wrapped endpoint uses.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import augur
from augur import analyze, catalog, config
from augur.events.outcomes import OUTCOME_TYPES
from augur.models import registry
from augur.replay import ReplayStore
from augur.scoring import race_inputs, scores

BENCH_RACES: tuple[str, ...] = ("2024-01-bahrain-grand-prix", "2024-24-abu-dhabi-grand-prix")
DATA_SOURCE = "openf1"


class BenchError(Exception):
    pass


def default_out_dir() -> Path:
    return catalog.REPO_ROOT / "bench"


def check(data_dir: Path, model_name: str, races: Sequence[str]) -> dict:
    """Refuse an unknown model, a missing race, or a model trained on a benchmark race.

    Returns the model's metrics (for its author).
    """
    try:
        registry.get_model_class(model_name)
    except registry.UnknownModelError:
        raise BenchError(f"unknown model {model_name}") from None
    store = ReplayStore(data_dir)
    for race_id in races:
        if store.get_race(race_id) is None:
            raise BenchError(f"missing race {race_id}, run augur.ingest first")
    try:
        metrics = registry.read_metrics(data_dir, model_name)
    except registry.ModelNotTrainedError as exc:
        raise BenchError(str(exc)) from None
    for race_id in races:
        if race_id in metrics.get("train_races", []):
            raise BenchError(f"benchmark race {race_id} is in the training set")
    return metrics


def needs_analysis(store: ReplayStore, race_id: str, model_name: str) -> bool:
    if not store.is_analyzed(race_id, model_name) or not store.has_positions(race_id, model_name):
        return True
    race = store.get_race(race_id)
    events = store.events_until(race_id, model_name, int(race["total_laps"]))
    # Analyzed before outcomes existed: every outcome-type event would read as pending.
    return any(e["type"] in OUTCOME_TYPES and e["outcome"] is None for e in events)


def ensure_analyzed(data_dir: Path, race_id: str, model_name: str, runs: int) -> bool:
    if not needs_analysis(ReplayStore(data_dir), race_id, model_name):
        return False
    seed = config.POSITION_SEED_DEFAULT
    try:
        events, positions = analyze.compute_analysis(data_dir, race_id, model_name, runs=runs, seed=seed)
    except analyze.AnalyzeError as exc:
        raise BenchError(str(exc)) from None
    analyze.replace_events(data_dir, race_id, model_name, events)
    analyze.replace_positions(data_dir, race_id, model_name, positions, runs, seed)
    return True


SCORE_KEYS = (
    "position_skill_pct", "brier_model", "brier_baseline",
    "lap_improvement_pct", "mae_model_s", "mae_baseline_s", "hit_rate",
)


def run_bench(
    model_name: str,
    data_dir: Path,
    *,
    races: Sequence[str] = BENCH_RACES,
    runs: int = config.POSITION_RUNS_DEFAULT,
) -> dict:
    metrics = check(data_dir, model_name, races)
    for race_id in races:
        ensure_analyzed(data_dir, race_id, model_name, runs)
    inputs = [race_inputs(data_dir, race_id, model_name) for race_id in races]
    pooled = scores(inputs)
    per_race = [{"race_id": i.race_id, **{k: s[k] for k in SCORE_KEYS}} for i, s in ((i, scores([i])) for i in inputs)]
    author = metrics.get("author") or getattr(registry.get_model_class(model_name), "author", None)
    return {
        "model": model_name,
        "author": author,
        "races": list(races),
        **{k: pooled[k] for k in SCORE_KEYS},
        "per_race": per_race,
        "seed": config.POSITION_SEED_DEFAULT,
        "data_source": DATA_SOURCE,
        "augur_version": augur.__version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def summary_line(result: dict) -> str:
    skill = result["position_skill_pct"]
    podium = "podium skill n/a" if skill is None else f"podium skill {skill:.1f}% vs current order"
    improvement = result["lap_improvement_pct"]
    if improvement is None:
        laps = "lap times n/a"
    elif improvement > 0:
        laps = f"lap times beat baseline by {improvement:.1f}%"
    elif improvement < 0:
        laps = f"lap times trail baseline by {-improvement:.1f}%"
    else:
        laps = "lap times match baseline (0.0%)"
    hr = result["hit_rate"]
    pct = "n/a" if hr["overall_pct"] is None else f"{hr['overall_pct']:.0f}%"
    return f"{result['model']}: {podium}, {laps}, event hit rate {pct} ({hr['hits']}/{hr['resolved']})"


def write_result(result: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result['model']}.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return path


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m augur.bench", description="Score a model on the benchmark races.")
    p.add_argument("--model", required=True)
    p.add_argument("--data-dir", type=Path, default=None, help="data root (default: repo data/)")
    p.add_argument("--out-dir", type=Path, default=None, help="result directory (default: repo bench/)")
    p.add_argument(
        "--runs",
        type=int,
        default=config.POSITION_RUNS_DEFAULT,
        help=f"position simulation runs per lap when a race must be analyzed "
        f"({config.POSITION_RUNS_MIN}..{config.POSITION_RUNS_MAX})",
    )
    return p


def main(argv: Sequence[str] | None = None, *, races: Sequence[str] = BENCH_RACES) -> int:
    args = _parser().parse_args(argv)
    data_dir: Path = args.data_dir if args.data_dir is not None else catalog.default_data_dir()
    out_dir: Path = args.out_dir if args.out_dir is not None else default_out_dir()
    if not config.POSITION_RUNS_MIN <= args.runs <= config.POSITION_RUNS_MAX:
        print(f"runs must be {config.POSITION_RUNS_MIN}..{config.POSITION_RUNS_MAX}", flush=True)
        return 1
    try:
        result = run_bench(args.model, data_dir, races=races, runs=args.runs)
    except BenchError as exc:
        print(str(exc), flush=True)
        return 1
    write_result(result, out_dir)
    print(summary_line(result), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
