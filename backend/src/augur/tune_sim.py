"""Tune the position simulator's pace-offset and model-delta-decay constants.

Usage:
    python -m augur.tune_sim --model <name> [--data-dir DIR] [--runs N]

Simulates only the checkpoint laps of the evaluation races (``augur.bench.EVAL_ROUNDS``,
2024 rounds 12 to 23, never the benchmark races) for every combination of
PACE_OFFSET_GRID x DELTA_DECAY_GRID and prints one line per combination:

    offset_sd=<x> decay=<y> brier=<b> log_loss=<l>

with the pooled podium Brier score and log loss over all checkpoint pairs. The values
with the lowest Brier score (log loss breaks ties) go into ``augur.config`` by hand.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from augur import catalog, config
from augur.bench import EVAL_ROUNDS, BenchError, check, resolve_rounds
from augur.feed import ReplayFeed
from augur.models import registry
from augur.positions import prepare, simulate_finish, summarize
from augur.priors import circuit_priors
from augur.replay import ReplayStore
from augur.scoring import PODIUM, checkpoints, log_loss, podium_pairs, podium_skill
from augur.state import positions_by_lap

PACE_OFFSET_GRID: tuple[float, ...] = (0.05, 0.10, 0.15, 0.20, 0.30)
DELTA_DECAY_GRID: tuple[float, ...] = (0.3, 0.5, 0.7)


@contextmanager
def constants(offset_sd: float, decay: float) -> Iterator[None]:
    """Temporarily set PACE_OFFSET_SD_S and MODEL_DELTA_DECAY (restored afterwards)."""
    saved = (config.PACE_OFFSET_SD_S, config.MODEL_DELTA_DECAY)
    config.PACE_OFFSET_SD_S, config.MODEL_DELTA_DECAY = float(offset_sd), float(decay)
    try:
        yield
    finally:
        config.PACE_OFFSET_SD_S, config.MODEL_DELTA_DECAY = saved


def _prepared(data_dir: Path, race_ids: Sequence[str], model_name: str) -> list[dict]:
    """Per race: checkpoint states, running orders, and the final podium."""
    store = ReplayStore(data_dir)
    model = registry.load_trained(data_dir, model_name)
    out = []
    for race_id in race_ids:
        total = int(store.get_race(race_id)["total_laps"])
        cps = checkpoints(total)
        feed = ReplayFeed(race_id, store)
        prior = circuit_priors(store, race_id)
        meta = {"race_id": race_id, "total_laps": total}
        order = positions_by_lap(store.laps_until(race_id, total), store.list_drivers(race_id), meta, [*cps, total])
        out.append(
            {
                "total": total,
                "checkpoints": {c: prepare(feed, c, model, prior) for c in cps},
                "order": {c: order[c] for c in cps},
                "podium": [code for code, pos in order[total].items() if pos <= PODIUM],
            }
        )
    return out


def grid_scores(
    races: list[dict], runs: int, seed: int = config.POSITION_SEED_DEFAULT
) -> list[tuple[float, float, float | None, float | None]]:
    """(offset_sd, decay, pooled brier, pooled log loss) per grid combination, in grid order."""
    rows = []
    for offset_sd in PACE_OFFSET_GRID:
        for decay in DELTA_DECAY_GRID:
            pairs = []
            with constants(offset_sd, decay):
                for race in races:
                    p_podium = {}
                    for c, (starts, loss) in race["checkpoints"].items():
                        if not starts:
                            continue
                        codes = [s.code for s in starts]
                        result = summarize(codes, simulate_finish(starts, c, race["total"], runs, seed, loss))
                        p_podium[c] = {r["code"]: r["p_podium"] for r in result}
                    pairs += podium_pairs(race["order"], p_podium, race["podium"])
            brier = podium_skill(pairs)["brier_model"]
            rows.append((offset_sd, decay, brier, log_loss([m for m, _, _ in pairs], [o for _, _, o in pairs])))
    return rows


def format_row(row: tuple[float, float, float | None, float | None]) -> str:
    offset_sd, decay, brier, ll = row
    return f"offset_sd={offset_sd:.2f} decay={decay:.1f} brier={brier} log_loss={ll}"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m augur.tune_sim", description="Grid-search simulator constants on the evaluation races."
    )
    p.add_argument("--model", required=True)
    p.add_argument("--data-dir", type=Path, default=None, help="data root (default: repo data/)")
    p.add_argument(
        "--runs", type=int, default=config.POSITION_RUNS_DEFAULT,
        help=f"simulation runs per checkpoint ({config.POSITION_RUNS_MIN}..{config.POSITION_RUNS_MAX})",
    )
    return p


def main(argv: Sequence[str] | None = None, *, eval_rounds: Sequence[tuple[int, int]] = EVAL_ROUNDS) -> int:
    args = _parser().parse_args(argv)
    data_dir: Path = args.data_dir if args.data_dir is not None else catalog.default_data_dir()
    if not config.POSITION_RUNS_MIN <= args.runs <= config.POSITION_RUNS_MAX:
        print(f"runs must be {config.POSITION_RUNS_MIN}..{config.POSITION_RUNS_MAX}", flush=True)
        return 1
    try:
        try:
            registry.get_model_class(args.model)
        except registry.UnknownModelError:
            raise BenchError(f"unknown model {args.model}") from None
        race_ids = resolve_rounds(data_dir, eval_rounds)
        check(data_dir, args.model, race_ids)
    except BenchError as exc:
        print(str(exc), flush=True)
        return 1
    for row in grid_scores(_prepared(data_dir, race_ids, args.model), args.runs):
        print(format_row(row), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
