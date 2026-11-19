import re
import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest

from augur import catalog
from augur.ingest import main


def fake_laps():
    rows = []
    for code, team in (("VER", "Red Bull Racing"), ("LEC", "Ferrari")):
        for lap in (1, 2):
            rows.append(
                {
                    "Driver": code, "Team": team, "LapNumber": float(lap),
                    "LapTime": pd.Timedelta(seconds=95 + lap), "Time": pd.Timedelta(minutes=55 + lap),
                    "Stint": 1.0, "Compound": "SOFT", "TyreLife": float(lap),
                    "PitInTime": pd.NaT, "PitOutTime": pd.NaT, "TrackStatus": "1", "IsAccurate": True,
                }
            )
    return pd.DataFrame(rows)


def fake_session():
    results = pd.DataFrame(
        {
            "Abbreviation": ["VER", "LEC"],
            "FullName": ["Max Verstappen", "Charles Leclerc"],
            "TeamName": ["Red Bull Racing", "Ferrari"],
            "TeamColor": ["3671C6", float("nan")],
            "GridPosition": [1.0, 4.0],
        }
    )
    event = pd.Series({"EventName": "Bahrain Grand Prix", "Location": "Sakhir",
                       "EventDate": pd.Timestamp("2024-03-02")})
    return SimpleNamespace(event=event, laps=fake_laps(), results=results,
                           date=pd.Timestamp("2024-03-02 18:00"))


def stub_loader(year, round_, data_dir):
    if round_ == 99:
        raise ValueError("Invalid round 99")
    return fake_session()


def db_rows(data_dir, sql):
    with sqlite3.connect(catalog.db_path(data_dir)) as conn:
        return conn.execute(sql).fetchall()


def test_cli_success_and_failed_round(tmp_path, capsys):
    code = main(["--year", "2024", "--rounds", "1", "99", "--data-dir", str(tmp_path)],
                load_session=stub_loader)
    out = capsys.readouterr().out
    assert code == 1
    assert "ingested 2024-01-bahrain-grand-prix: 2 drivers, 2 laps" in out
    assert "failed 2024 round 99:" in out
    assert [p.name for p in (tmp_path / "races").iterdir()] == ["2024-01-bahrain-grand-prix"]
    assert db_rows(tmp_path, "SELECT race_id, round, location, date FROM races") == [
        ("2024-01-bahrain-grand-prix", 1, "Sakhir", "2024-03-02")
    ]
    assert db_rows(tmp_path, "SELECT code, team_color, grid_position FROM drivers ORDER BY code") == [
        ("LEC", "#71717A", 4), ("VER", "#3671C6", 1)
    ]


def test_cli_all_succeed_exit_zero(tmp_path, capsys):
    assert main(["--year", "2024", "--rounds", "1", "--data-dir", str(tmp_path)], load_session=stub_loader) == 0
    assert main(["--year", "2024", "--rounds", "1", "--data-dir", str(tmp_path)], load_session=stub_loader) == 0
    assert db_rows(tmp_path, "SELECT COUNT(*) FROM races") == [(1,)]
    assert db_rows(tmp_path, "SELECT COUNT(*) FROM drivers") == [(2,)]


def test_cli_normalize_failure_writes_nothing(tmp_path, capsys):
    def broken(year, round_, data_dir):
        s = fake_session()
        s.laps = s.laps.drop(columns=["LapTime"])
        return s

    assert main(["--year", "2024", "--rounds", "1", "--data-dir", str(tmp_path)], load_session=broken) == 1
    out = capsys.readouterr().out
    assert "failed 2024 round 1:" in out and "LapTime" in out
    assert not (tmp_path / "races").exists() or not any((tmp_path / "races").iterdir())


@pytest.mark.parametrize(
    "argv",
    [["--year", "abc", "--rounds", "1"], ["--year", "2024", "--rounds", "0"],
     ["--year", "2024", "--rounds", "100"], ["--year", "2024", "--rounds", "x"],
     ["--year", "2024"], ["--rounds", "1"]],
)
def test_cli_rejects_bad_input(tmp_path, argv):
    with pytest.raises(SystemExit) as exc:
        main(argv + ["--data-dir", str(tmp_path)], load_session=stub_loader)
    assert exc.value.code == 2


@pytest.mark.network
def test_network_ingest_2024_round_1(tmp_path, capsys):
    assert main(["--year", "2024", "--rounds", "1", "--data-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "ingested 2024-01-bahrain-grand-prix:" in out
    ((race_id, location, total_laps),) = db_rows(tmp_path, "SELECT race_id, location, total_laps FROM races")
    assert race_id == "2024-01-bahrain-grand-prix"
    assert location == "Sakhir"
    assert total_laps == 57
    colors = db_rows(tmp_path, "SELECT team_color FROM drivers")
    assert len(colors) == 20
    assert all(re.fullmatch(r"^#[0-9A-Fa-f]{6}$", c) for (c,) in colors)
    laps = pd.read_parquet(catalog.laps_path(tmp_path, race_id))
    assert laps["lap"].max() == 57
    assert laps["lap_time_s"].notna().sum() > 1000
