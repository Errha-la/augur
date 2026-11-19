import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="run tests marked 'network' (they download real OpenF1 data)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-network"):
        return
    skip = pytest.mark.skip(reason="network test; use --run-network to run")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


# --- Synthetic race fixture -------------------------------------------------

from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402

import pandas as pd  # noqa: E402

from augur import catalog  # noqa: E402
from augur.schema import LAP_COLUMNS  # noqa: E402

FIXTURE_RACE_ID = "2099-01-fixture-grand-prix"
FIXTURE_TOTAL_LAPS = 5
FIXTURE_DRIVERS = (
    # code, full_name, team, team_color, grid_position
    ("AAA", "Alpha Driver", "Red Team", "#3671C6", 1),
    ("BBB", "Bravo Driver", "Green Team", "#229971", 2),
    ("CCC", "Charlie Driver", "Grey Team", "#71717A", 3),
)


@dataclass(frozen=True)
class FixtureRace:
    data_dir: Path
    race_id: str
    total_laps: int
    driver_codes: tuple[str, ...]


def fixture_laps() -> pd.DataFrame:
    """15 rows: 3 drivers x 5 laps in the normalized lap schema.

    AAA leads on mediums; BBB pits at the end of lap 2 (stint 2 from lap 3);
    CCC has a missing lap time on lap 4. Lap 3 is under yellow ("2").
    """
    base = {"AAA": 90.0, "BBB": 91.0, "CCC": 92.5}
    team = {code: t for code, _, t, _, _ in FIXTURE_DRIVERS}
    rows = []
    for code in ("AAA", "BBB", "CCC"):
        session = 3600.0
        for lap in range(1, FIXTURE_TOTAL_LAPS + 1):
            lap_time = base[code] + 0.1 * lap
            if code == "BBB" and lap in (2, 3):
                lap_time += 20.0  # pit in / pit out laps
            session += lap_time
            if code == "BBB":
                stint, compound = (1, "SOFT") if lap <= 2 else (2, "HARD")
                tyre_life = lap if lap <= 2 else lap - 2
            elif code == "CCC":
                stint, compound, tyre_life = 1, "HARD", lap
            else:
                stint, compound, tyre_life = 1, "MEDIUM", lap
            rows.append(
                {
                    "driver": code,
                    "team": team[code],
                    "lap": lap,
                    "lap_time_s": None if (code == "CCC" and lap == 4) else lap_time,
                    "session_time_s": session,
                    "stint": stint,
                    "compound": compound,
                    "tyre_life": tyre_life,
                    "pit_in": code == "BBB" and lap == 2,
                    "pit_out": code == "BBB" and lap == 3,
                    "track_status": "2" if lap == 3 else "1",
                    "is_accurate": not (code == "BBB" and lap in (2, 3)),
                }
            )
    df = pd.DataFrame(rows, columns=list(LAP_COLUMNS))
    return df.astype(
        {
            "driver": "object",
            "team": "object",
            "lap": "int64",
            "lap_time_s": "float64",
            "session_time_s": "float64",
            "stint": "int64",
            "compound": "object",
            "tyre_life": "Int64",
            "pit_in": "bool",
            "pit_out": "bool",
            "track_status": "object",
            "is_accurate": "bool",
        }
    )


def write_race(
    data_dir: Path,
    race_id: str,
    laps: pd.DataFrame,
    *,
    year: int,
    round_: int,
    event_name: str,
    total_laps: int,
    drivers=FIXTURE_DRIVERS,
    location: str = "Nowhere",
) -> None:
    """Write laps.parquet and register the race + drivers in the catalog."""
    path = catalog.laps_path(data_dir, race_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    laps.to_parquet(path, index=False)
    conn = catalog.connect(data_dir)
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO races VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (race_id, year, round_, event_name, location,
                 f"{year}-01-01", total_laps, "2026-01-01T00:00:00Z"),
            )
            conn.executemany(
                "INSERT OR REPLACE INTO drivers VALUES (?, ?, ?, ?, ?, ?)",
                [(race_id, code, name, team, color, grid)
                 for code, name, team, color, grid in drivers],
            )
    finally:
        conn.close()


@pytest.fixture
def fixture_race(tmp_path) -> FixtureRace:
    """A synthetic 3-driver, 5-lap race in a temporary data directory."""
    data_dir = tmp_path / "data"
    write_race(
        data_dir,
        FIXTURE_RACE_ID,
        fixture_laps(),
        year=2099,
        round_=1,
        event_name="Fixture Grand Prix",
        total_laps=FIXTURE_TOTAL_LAPS,
    )
    return FixtureRace(
        data_dir=data_dir,
        race_id=FIXTURE_RACE_ID,
        total_laps=FIXTURE_TOTAL_LAPS,
        driver_codes=tuple(d[0] for d in FIXTURE_DRIVERS),
    )
