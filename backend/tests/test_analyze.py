import sqlite3

import pytest
from synthetic import write_synthetic_race

from augur import analyze, catalog, train

RACE = "2098-03-synthetic-grand-prix"


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "data"
    for rnd, seed in ((1, 1), (2, 2), (3, 3)):
        write_synthetic_race(d, 2098, rnd, seed)
    train.train("baseline", [(2098, 1), (2098, 2)], [(2098, 3)], d)
    return d


def count(d, race=RACE, model="baseline"):
    with sqlite3.connect(catalog.db_path(d)) as conn:
        return conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT id) FROM events WHERE race_id = ? AND model = ?", (race, model)
        ).fetchone()


def test_rerun_analysis_stores_events_once(data, capsys):
    assert analyze.main(["--race", RACE, "--model", "baseline", "--data-dir", str(data)]) == 0
    first = count(data)
    assert analyze.main(["--race", RACE, "--model", "baseline", "--data-dir", str(data)]) == 0
    assert count(data) == first
    assert first[0] == first[1] > 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[-1] == f"analyzed {RACE}: {first[0]} events"


def test_training_race_refused(data, capsys):
    race = "2098-01-synthetic-grand-prix"
    assert analyze.main(["--race", race, "--model", "baseline", "--data-dir", str(data)]) == 1
    assert "training set" in capsys.readouterr().out
    assert count(data, race) == (0, 0)


def test_missing_model_file(data, capsys):
    assert analyze.main(["--race", RACE, "--model", "lightgbm", "--data-dir", str(data)]) == 1
    assert capsys.readouterr().out.strip() == "model lightgbm is not trained, run augur.train first"


def test_unknown_model_and_race(data, capsys):
    assert analyze.main(["--race", RACE, "--model", "nope", "--data-dir", str(data)]) == 1
    assert analyze.main(["--race", "2098-09-nope", "--model", "baseline", "--data-dir", str(data)]) == 1
    out = capsys.readouterr().out
    assert "unknown model nope" in out and "race not found" in out
