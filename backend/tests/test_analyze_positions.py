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


def test_old_database_gains_distribution_column(trained, monkeypatch):
    from fastapi.testclient import TestClient

    from augur.api import create_app
    from augur.replay import ReplayStore

    # Rebuild position_predictions as it was before position_distribution existed.
    with sqlite3.connect(catalog.db_path(trained.data_dir)) as conn:
        conn.execute("DROP TABLE IF EXISTS position_predictions")
        conn.execute(
            "CREATE TABLE position_predictions (race_id TEXT, model TEXT, lap INT, code TEXT, p_win REAL,"
            " p_podium REAL, p_points REAL, expected_position REAL, position_p10 REAL, position_p90 REAL,"
            " runs INT, seed INT, PRIMARY KEY (race_id, model, lap, code))"
        )
        conn.execute(
            "INSERT INTO position_predictions VALUES ('old-race', 'baseline', 1, 'AAA', 1, 1, 1, 1, 1, 1, 200, 42)"
        )
    assert run(trained) == 0
    with sqlite3.connect(catalog.db_path(trained.data_dir)) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(position_predictions)")}
    assert "position_distribution" in cols

    store = ReplayStore(trained.data_dir)
    old = store.positions_until("old-race", "baseline", 1, include_distribution=True)
    assert old[0]["position_distribution"] is None
    new = store.positions_until(trained.race_id, "baseline", 3, only_lap=True, include_distribution=True)
    n = len(trained.driver_codes)
    assert new and all(len(r["position_distribution"]) == n for r in new)
    assert "position_distribution" not in store.positions_until(trained.race_id, "baseline", 3)[0]

    monkeypatch.setenv("AUGUR_MODEL", "baseline")
    body = TestClient(create_app(trained.data_dir)).get(f"/api/races/{trained.race_id}/positions?lap=3").json()
    assert set(body["drivers"][0]) == {
        "code", "p_win", "p_podium", "p_points", "expected_position", "position_p10", "position_p90"
    }
