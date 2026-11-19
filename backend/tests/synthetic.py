"""Larger synthetic races for model, strategy, and event tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from conftest import write_race

from augur.schema import LAP_COLUMNS

SYN_DRIVERS = (
    # code, team, base pace (s), pit lap
    ("AAA", "Red Team", 90.0, 14),
    ("BBB", "Red Team", 90.3, 16),
    ("CCC", "Green Team", 90.5, 12),
    ("DDD", "Green Team", 90.8, 18),
    ("EEE", "Grey Team", 91.0, 15),
    ("FFF", "Grey Team", 91.4, 13),
)
SYN_DEG = {"MEDIUM": 0.08, "HARD": 0.04}
SYN_DRIVER_ROWS = tuple((code, code, team, "#71717A", None) for code, team, _, _ in SYN_DRIVERS)


def synthetic_race_laps(seed: int, total_laps: int = 30) -> pd.DataFrame:
    """6 drivers, one stop each (MEDIUM -> HARD), slow lap 1, small noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for code, team, base, pit_lap in SYN_DRIVERS:
        session = 0.0
        for lap in range(1, total_laps + 1):
            stint = 1 if lap <= pit_lap else 2
            compound = "MEDIUM" if stint == 1 else "HARD"
            tyre_life = lap if stint == 1 else lap - pit_lap
            t = base + SYN_DEG[compound] * tyre_life - 0.05 * lap + rng.normal(0, 0.15)
            if lap == 1:
                t += 6.0
            if lap == pit_lap:
                t += 10.0
            if lap == pit_lap + 1:
                t += 12.0
            session += t
            rows.append(
                {
                    "driver": code, "team": team, "lap": lap, "lap_time_s": round(t, 3),
                    "session_time_s": round(session, 3), "stint": stint, "compound": compound,
                    "tyre_life": tyre_life, "pit_in": lap == pit_lap, "pit_out": lap == pit_lap + 1,
                    "track_status": "1",
                    "is_accurate": lap > 1 and lap not in (pit_lap, pit_lap + 1),
                }
            )
    return pd.DataFrame(rows, columns=list(LAP_COLUMNS)).astype({"tyre_life": "Int64"})


def write_synthetic_race(data_dir: Path, year: int, round_: int, seed: int, total_laps: int = 30,
                         location: str = "Nowhere") -> str:
    race_id = f"{year}-{round_:02d}-synthetic-grand-prix"
    write_race(data_dir, race_id, synthetic_race_laps(seed, total_laps), year=year, round_=round_,
               event_name="Synthetic Grand Prix", total_laps=total_laps, drivers=SYN_DRIVER_ROWS,
               location=location)
    return race_id
