"""FastF1 race ingest: normalize laps, build catalog records, CLI.

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

import pandas as pd

from augur import catalog
from augur.schema import DEFAULT_TEAM_COLOR, LAP_COLUMNS
from augur.storage import DriverRecord, RaceRecord, store_race, validate_race_id

# FastF1 Laps columns read by normalize_laps.
SOURCE_COLUMNS: tuple[str, ...] = (
    "Driver",
    "Team",
    "LapNumber",
    "LapTime",
    "Time",
    "Stint",
    "Compound",
    "TyreLife",
    "PitInTime",
    "PitOutTime",
    "TrackStatus",
    "IsAccurate",
)

MIN_YEAR = 1950
MAX_YEAR = 2100
MIN_ROUND = 1
MAX_ROUND = 99

_HEX6 = re.compile(r"^[0-9A-Fa-f]{6}$")


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


# ---------------------------------------------------------------- normalization


def _seconds(series: pd.Series) -> pd.Series:
    """Timedelta -> float seconds; NaT -> NaN (null in parquet)."""
    return pd.to_timedelta(series).dt.total_seconds().astype("float64")


def _nullable_int(series: pd.Series, name: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="raise")
    try:
        return numeric.astype("Int64")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"column {name!r} has non-integer values") from exc


def _nullable_str(series: pd.Series) -> pd.Series:
    def conv(value: Any) -> str | None:
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            return None
        text = str(value)
        return text if text != "" else None

    return series.map(conv).astype("object")


def normalize_laps(fastf1_laps: pd.DataFrame) -> pd.DataFrame:
    """Map FastF1 Laps to the 12 normalized columns (order = LAP_COLUMNS).

    Durations become float seconds; missing values stay null (NaN / <NA> /
    None), never zero. `lap` must be present on every row; `stint` and
    `tyre_life` are nullable Int64 because FastF1 occasionally has NaN there.
    Raises KeyError naming any missing FastF1 column.
    """
    missing = [c for c in SOURCE_COLUMNS if c not in fastf1_laps.columns]
    if missing:
        raise KeyError(f"FastF1 laps missing column(s): {', '.join(missing)}")

    src = pd.DataFrame(fastf1_laps).reset_index(drop=True)

    lap = _nullable_int(src["LapNumber"], "LapNumber")
    if lap.isna().any():
        raise ValueError("column 'LapNumber' has missing values")
    driver = _nullable_str(src["Driver"])
    if driver.isna().any():
        raise ValueError("column 'Driver' has missing values")

    out = pd.DataFrame(
        {
            "driver": driver,
            "team": _nullable_str(src["Team"]),
            "lap": lap.astype("int64"),
            "lap_time_s": _seconds(src["LapTime"]),
            "session_time_s": _seconds(src["Time"]),
            "stint": _nullable_int(src["Stint"], "Stint"),
            "compound": _nullable_str(src["Compound"]),
            "tyre_life": _nullable_int(src["TyreLife"], "TyreLife"),
            "pit_in": src["PitInTime"].notna().astype("bool"),
            "pit_out": src["PitOutTime"].notna().astype("bool"),
            "track_status": _nullable_str(src["TrackStatus"]),
            "is_accurate": src["IsAccurate"].astype("boolean").fillna(False).astype("bool"),
        }
    )
    return out.loc[:, list(LAP_COLUMNS)]


# --------------------------------------------------------------- session records


def team_color(value: Any) -> str:
    """FastF1 TeamColor ('3671C6', maybe '#'-prefixed/empty/NaN) -> '#RRGGBB'."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return DEFAULT_TEAM_COLOR
    text = str(value).strip().lstrip("#")
    return f"#{text.upper()}" if _HEX6.fullmatch(text) else DEFAULT_TEAM_COLOR


def _opt_str(value: Any) -> str | None:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def build_drivers(results: pd.DataFrame) -> list[DriverRecord]:
    missing = [
        c
        for c in ("Abbreviation", "FullName", "TeamName", "TeamColor", "GridPosition")
        if c not in results.columns
    ]
    if missing:
        raise KeyError(f"FastF1 results missing column(s): {', '.join(missing)}")
    drivers: list[DriverRecord] = []
    for row in results.itertuples(index=False):
        code = _opt_str(row.Abbreviation)
        if code is None:
            continue
        drivers.append(
            DriverRecord(
                code=code,
                full_name=_opt_str(row.FullName),
                team=_opt_str(row.TeamName),
                team_color=team_color(row.TeamColor),
                grid_position=_opt_int(row.GridPosition),
            )
        )
    return drivers


def _session_date(session: Any) -> str | None:
    for value in (getattr(session, "date", None), session.event.get("EventDate")):
        if value is not None and not pd.isna(value):
            return pd.Timestamp(value).date().isoformat()
    return None


def build_race(session: Any, year: int, round_: int, laps: pd.DataFrame) -> RaceRecord:
    event = session.event
    event_name = _opt_str(event["EventName"])
    if event_name is None:
        raise ValueError("session has no EventName")
    if laps.empty:
        raise ValueError("session has no laps")
    return RaceRecord(
        race_id=make_race_id(year, round_, event_name),
        year=year,
        round=round_,
        event_name=event_name,
        location=_opt_str(event.get("Location")),
        date=_session_date(session),
        total_laps=int(laps["lap"].max()),
    )


def ingest_session(session: Any, year: int, round_: int, data_dir: Path) -> tuple[RaceRecord, list[DriverRecord]]:
    """Normalize a loaded session and store it. Returns what was stored."""
    laps = normalize_laps(session.laps)
    race = build_race(session, year, round_, laps)
    drivers = build_drivers(session.results)
    if not drivers:
        raise ValueError("session has no driver results")
    store_race(data_dir, race, drivers, laps)
    return race, drivers


# ------------------------------------------------------------------------- CLI

SessionLoader = Callable[[int, int, Path], Any]


def load_fastf1_session(year: int, round_: int, data_dir: Path) -> Any:
    """Load the race ("R") session of a round via FastF1 with a local cache."""
    import fastf1

    cache_dir = catalog.fastf1_cache_dir(data_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    session = fastf1.get_session(year, round_, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    return session


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
    p = argparse.ArgumentParser(prog="python -m augur.ingest", description="Ingest F1 races from FastF1.")
    p.add_argument("--year", type=_year_arg, required=True)
    p.add_argument("--rounds", type=_round_arg, nargs="+", required=True)
    p.add_argument("--data-dir", type=Path, default=None, help="data root (default: repo data/)")
    return p


def main(argv: Sequence[str] | None = None, load_session: SessionLoader | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir: Path = args.data_dir if args.data_dir is not None else catalog.default_data_dir()
    loader = load_session or load_fastf1_session
    ok = True
    for round_ in dict.fromkeys(args.rounds):  # de-duplicate, keep order
        try:
            session = loader(args.year, round_, data_dir)
            race, drivers = ingest_session(session, args.year, round_, data_dir)
        except Exception as exc:  # report and continue with the next round
            ok = False
            reason = str(exc) or type(exc).__name__
            print(f"failed {args.year} round {round_}: {type(exc).__name__}: {reason}", flush=True)
            continue
        print(f"ingested {race.race_id}: {len(drivers)} drivers, {race.total_laps} laps", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
