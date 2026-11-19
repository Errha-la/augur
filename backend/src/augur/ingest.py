"""OpenF1 race ingest CLI: resolve rounds, normalize laps, store races.

Usage:
    python -m augur.ingest --year 2024 --rounds 1 2 3 [--data-dir DIR]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from augur import catalog
from augur.openf1 import RacePayload, load_openf1_race, normalize_openf1, parse_time
from augur.storage import DriverRecord, RaceRecord, store_race, validate_race_id

MIN_YEAR = 1950
MAX_YEAR = 2100
MIN_ROUND = 1
MAX_ROUND = 99


# --------------------------------------------------------------------------- ids


def slugify(text: str) -> str:
    """Lowercase; runs of non [a-z0-9] become '-'; trim '-'."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    if not slug:
        raise ValueError(f"event name {text!r} has no slug characters")
    return slug


def make_race_id(year: int, round_: int, event_name: str) -> str:
    year, round_ = _check_year(year), _check_round(round_)
    return validate_race_id(f"{year:04d}-{round_:02d}-{slugify(event_name)}")


def _check_year(year: Any) -> int:
    if isinstance(year, bool) or not isinstance(year, int):
        raise ValueError(f"year must be an int, got {year!r}")
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"year {year} outside {MIN_YEAR}..{MAX_YEAR}")
    return year


def _check_round(round_: Any) -> int:
    if isinstance(round_, bool) or not isinstance(round_, int):
        raise ValueError(f"round must be an int, got {round_!r}")
    if not MIN_ROUND <= round_ <= MAX_ROUND:
        raise ValueError(f"round {round_} outside {MIN_ROUND}..{MAX_ROUND}")
    return round_


# ----------------------------------------------------------------------- ingest


def ingest_payload(
    payload: RacePayload, year: int, round_: int, data_dir: Path
) -> tuple[RaceRecord, list[DriverRecord]]:
    """Normalize one round's OpenF1 payloads and store them atomically."""
    laps, drivers = normalize_openf1(
        payload.session, payload.laps, payload.stints, payload.pits, payload.drivers, payload.race_control
    )
    if laps.empty:
        raise ValueError("session has no laps")
    if not drivers:
        raise ValueError("session has no drivers")
    session = payload.session
    location = session.get("location")
    race = RaceRecord(
        race_id=make_race_id(year, round_, payload.meeting_name),
        year=year,
        round=round_,
        event_name=payload.meeting_name,
        location=(location.strip() or None) if isinstance(location, str) else None,
        date=parse_time(session["date_start"], "session.date_start").date().isoformat(),
        total_laps=int(laps["lap"].max()),
    )
    store_race(data_dir, race, drivers, laps)
    return race, drivers


# ------------------------------------------------------------------------- CLI

RaceLoader = Callable[[int, int, Path], RacePayload]


def _year_arg(text: str) -> int:
    try:
        return _check_year(int(text, 10))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _round_arg(text: str) -> int:
    try:
        return _check_round(int(text, 10))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m augur.ingest", description="Ingest historical F1 races from the public OpenF1 API."
    )
    p.add_argument("--year", type=_year_arg, required=True)
    p.add_argument("--rounds", type=_round_arg, nargs="+", required=True)
    p.add_argument("--data-dir", type=Path, default=None, help="data root (default: repo data/)")
    return p


def _reason(exc: BaseException) -> str:
    if isinstance(exc, KeyError) and exc.args:
        text = str(exc.args[0])  # str(KeyError) would add quotes
    else:
        text = str(exc)
    return text or type(exc).__name__


def main(argv: Sequence[str] | None = None, load_race: RaceLoader | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir: Path = args.data_dir if args.data_dir is not None else catalog.default_data_dir()
    loader = load_race or load_openf1_race
    ok = True
    for round_ in dict.fromkeys(args.rounds):  # de-duplicate, keep order
        try:
            payload = loader(args.year, round_, data_dir)
            race, drivers = ingest_payload(payload, args.year, round_, data_dir)
        except Exception as exc:  # report and continue with the next round
            ok = False
            print(f"failed {args.year} round {round_}: {_reason(exc)}", flush=True)
            continue
        print(f"ingested {race.race_id}: {len(drivers)} drivers, {race.total_laps} laps", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
