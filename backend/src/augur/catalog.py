"""Data directory layout and the SQLite race catalog.

Layout under a data root:
    <root>/augur.sqlite                 races + drivers catalog
    <root>/races/<race_id>/laps.parquet normalized laps of one race
    <root>/openf1-cache/                OpenF1 JSON response cache
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# backend/src/augur/catalog.py -> repository root is three levels above "augur".
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR_ENV = "AUGUR_DATA_DIR"

SCHEMA = """
CREATE TABLE IF NOT EXISTS races (
    race_id     TEXT PRIMARY KEY,
    year        INT,
    round       INT,
    event_name  TEXT,
    location    TEXT,
    date        TEXT,
    total_laps  INT,
    ingested_at TEXT
);
CREATE TABLE IF NOT EXISTS drivers (
    race_id       TEXT,
    code          TEXT,
    full_name     TEXT,
    team          TEXT,
    team_color    TEXT,
    grid_position INT,
    PRIMARY KEY (race_id, code)
);
CREATE TABLE IF NOT EXISTS events (
    race_id   TEXT,
    model     TEXT,
    id        TEXT,
    lap       INT,
    type      TEXT,
    drivers   TEXT,
    severity  REAL,
    title     TEXT,
    analysis  TEXT,
    evidence  TEXT,
    PRIMARY KEY (race_id, model, id)
);
CREATE TABLE IF NOT EXISTS analyses (
    race_id     TEXT,
    model       TEXT,
    n_events    INT,
    analyzed_at TEXT,
    PRIMARY KEY (race_id, model)
);
"""


def default_data_dir() -> Path:
    """Data root: $AUGUR_DATA_DIR when set, else <repo>/data."""
    env = os.environ.get(DATA_DIR_ENV)
    return Path(env) if env else REPO_ROOT / "data"


def db_path(data_dir: Path) -> Path:
    return Path(data_dir) / "augur.sqlite"


def race_dir(data_dir: Path, race_id: str) -> Path:
    return Path(data_dir) / "races" / race_id


def laps_path(data_dir: Path, race_id: str) -> Path:
    return race_dir(data_dir, race_id) / "laps.parquet"


def openf1_cache_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "openf1-cache"


def connect(data_dir: Path) -> sqlite3.Connection:
    """Open the catalog, creating the file and tables when missing."""
    path = db_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
