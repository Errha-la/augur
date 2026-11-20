import sqlite3

import pytest
from synthetic import write_synthetic_race

from augur import analyze, catalog, train


@pytest.fixture
def trained(fixture_race):
    """fixture_race plus a baseline model trained on two synthetic races in the same data dir."""
    d = fixture_race.data_dir
    for rnd, seed in ((1, 1), (2, 2)):
        write_synthetic_race(d, 2098, rnd, seed)
    train.train("baseline", [(2098, 1)], [(2098, 2)], d)
    return fixture_race


def rows(race):
    with sqlite3.connect(catalog.db_path(race.data_dir)) as conn:
        return conn.execute(
            "SELECT lap, code, runs, seed FROM position_predictions WHERE race_id = ? AND model = 'baseline'",
            (race.race_id,),
        ).fetchall()


def run(race, *extra):
    return analyze.main(
        ["--race", race.race_id, "--model", "baseline", "--data-dir", str(race.data_dir), "--runs", "200", *extra]
    )


def test_analyze_twice_keeps_one_row_per_lap_and_driver(trained, capsys):
    assert run(trained) == 0
    first = rows(trained)
    assert run(trained) == 0
    second = rows(trained)
    assert len(second) == len(first) == len({(lap, code) for lap, code, _, _ in second})
    assert {lap for lap, *_ in second} == set(range(1, trained.total_laps + 1))
    assert {code for _, code, _, _ in second} == set(trained.driver_codes)
    assert {(r, s) for *_, r, s in second} == {(200, 42)}
    out = capsys.readouterr().out
    assert f"position predictions: {trained.total_laps} laps, 200 runs per lap" in out


def test_invalid_runs_refused(trained, capsys):
    assert analyze.main(
        ["--race", trained.race_id, "--model", "baseline", "--data-dir", str(trained.data_dir), "--runs", "5"]
    ) == 1
    assert "runs must be" in capsys.readouterr().out
    assert rows(trained) == []
