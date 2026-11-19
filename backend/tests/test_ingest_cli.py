import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from augur import catalog
from augur.ingest import main, make_race_id, slugify
from augur.openf1 import RacePayload, resolve_race_session

T0 = datetime(2024, 3, 2, 15, 0, tzinfo=timezone.utc)


def iso(seconds):
    return (T0 + timedelta(seconds=seconds)).isoformat()


def fake_payload(session_key=9472, meeting_name="Bahrain Grand Prix"):
    drivers = [
        {"driver_number": 1, "name_acronym": "VER", "full_name": "Max VERSTAPPEN",
         "team_name": "Red Bull Racing", "team_colour": "3671c6"},
        {"driver_number": 16, "name_acronym": "LEC", "full_name": "Charles LECLERC",
         "team_name": "Ferrari", "team_colour": None},
    ]
    laps, stints = [], []
    for number in (1, 16):
        for n in (1, 2):
            laps.append({"driver_number": number, "lap_number": n, "date_start": iso(95.0 * (n - 1)),
                         "lap_duration": 95.0 + n, "is_pit_out_lap": False})
        stints.append({"driver_number": number, "stint_number": 1, "lap_start": 1, "lap_end": 2,
                       "compound": "SOFT", "tyre_age_at_start": 0})
    session = {"session_key": session_key, "meeting_key": 1229, "date_start": "2024-03-02T15:00:00+00:00",
               "location": "Sakhir", "is_cancelled": False}
    return RacePayload(session=session, meeting_name=meeting_name, laps=laps, stints=stints, pits=[],
                       drivers=drivers, race_control=[])


def stub_loader(year, round_, data_dir):
    if round_ == 99:
        raise LookupError(f"no race session for round {round_}")
    return fake_payload()


def db_rows(data_dir, sql):
    with sqlite3.connect(catalog.db_path(data_dir)) as conn:
        return conn.execute(sql).fetchall()


def run(tmp_path, *rounds, loader=stub_loader):
    argv = ["--year", "2024", "--rounds", *map(str, rounds), "--data-dir", str(tmp_path)]
    return main(argv, load_race=loader)


def test_cli_success_and_failed_round(tmp_path, capsys):
    assert run(tmp_path, 1, 99) == 1
    out = capsys.readouterr().out
    assert "ingested 2024-01-bahrain-grand-prix: 2 drivers, 2 laps" in out
    assert "failed 2024 round 99: no race session for round 99" in out
    assert [p.name for p in (tmp_path / "races").iterdir()] == ["2024-01-bahrain-grand-prix"]
    assert db_rows(tmp_path, "SELECT race_id, year, round, event_name, location, date, total_laps FROM races") == [
        ("2024-01-bahrain-grand-prix", 2024, 1, "Bahrain Grand Prix", "Sakhir", "2024-03-02", 2)
    ]
    assert db_rows(tmp_path, "SELECT code, full_name, team, team_color, grid_position FROM drivers ORDER BY code") == [
        ("LEC", "Charles LECLERC", "Ferrari", "#71717A", None),
        ("VER", "Max VERSTAPPEN", "Red Bull Racing", "#3671C6", None),
    ]
    assert db_rows(tmp_path, "SELECT COUNT(*) FROM races WHERE round = 99") == [(0,)]
    laps = pd.read_parquet(catalog.laps_path(tmp_path, "2024-01-bahrain-grand-prix"))
    assert len(laps) == 4


def test_cli_reingest_twice_no_duplicates(tmp_path, capsys):
    assert run(tmp_path, 1) == 0
    assert run(tmp_path, 1) == 0
    assert db_rows(tmp_path, "SELECT COUNT(*) FROM races WHERE race_id = '2024-01-bahrain-grand-prix'") == [(1,)]
    assert db_rows(tmp_path, "SELECT race_id, code FROM drivers GROUP BY race_id, code HAVING COUNT(*) > 1") == []
    assert db_rows(tmp_path, "SELECT COUNT(*) FROM drivers") == [(2,)]


def test_cli_normalize_failure_writes_nothing(tmp_path, capsys):
    def broken(year, round_, data_dir):
        payload = fake_payload()
        for item in payload.laps:
            del item["lap_duration"]
        return payload

    assert run(tmp_path, 1, loader=broken) == 1
    out = capsys.readouterr().out
    assert re.search(r"^failed 2024 round 1: .*lap_duration", out, re.M)
    assert not (tmp_path / "races").exists() or not any((tmp_path / "races").iterdir())
    assert not catalog.db_path(tmp_path).exists() or db_rows(tmp_path, "SELECT COUNT(*) FROM races") == [(0,)]


def test_cli_rounds_resolve_from_calendar_skipping_cancelled(tmp_path, capsys):
    sessions = [
        {"session_key": 1, "meeting_key": 1, "date_start": "2024-03-02T15:00:00+00:00", "location": "A",
         "is_cancelled": False},
        {"session_key": 2, "meeting_key": 2, "date_start": "2024-03-09T15:00:00+00:00", "location": "B",
         "is_cancelled": True},
        {"session_key": 3, "meeting_key": 3, "date_start": "2024-03-16T15:00:00+00:00", "location": "C",
         "is_cancelled": False},
    ]
    names = {1: "Alpha Grand Prix", 2: "Bravo Grand Prix", 3: "Charlie Grand Prix"}

    def loader(year, round_, data_dir):
        session = resolve_race_session(sessions, round_)
        payload = fake_payload(session["session_key"], names[session["meeting_key"]])
        return RacePayload(**{**payload.__dict__, "session": {**payload.session, **session}})

    assert run(tmp_path, 1, 2, 3, loader=loader) == 1
    out = capsys.readouterr().out
    assert "ingested 2024-01-alpha-grand-prix:" in out
    assert "ingested 2024-02-charlie-grand-prix:" in out
    assert "failed 2024 round 3: no race session for round 3" in out
    assert db_rows(tmp_path, "SELECT race_id, location FROM races ORDER BY round") == [
        ("2024-01-alpha-grand-prix", "A"), ("2024-02-charlie-grand-prix", "C")
    ]


@pytest.mark.parametrize(
    "argv",
    [["--year", "abc", "--rounds", "1"], ["--year", "2024", "--rounds", "0"],
     ["--year", "2024", "--rounds", "100"], ["--year", "2024", "--rounds", "x"],
     ["--year", "2024", "--rounds", "1.5"], ["--year", "1800", "--rounds", "1"],
     ["--year", "2024"], ["--rounds", "1"]],
)
def test_cli_rejects_bad_input(tmp_path, argv):
    with pytest.raises(SystemExit) as exc:
        main(argv + ["--data-dir", str(tmp_path)], load_race=stub_loader)
    assert exc.value.code == 2


# ----------------------------------------------------------------- race ids


@pytest.mark.parametrize(
    ("year", "rnd", "name", "expected"),
    [
        (2024, 1, "Bahrain Grand Prix", "2024-01-bahrain-grand-prix"),
        (2023, 11, "Hungarian Grand Prix", "2023-11-hungarian-grand-prix"),
        (2024, 24, "Abu Dhabi Grand Prix", "2024-24-abu-dhabi-grand-prix"),
    ],
)
def test_race_id(year, rnd, name, expected):
    assert make_race_id(year, rnd, name) == expected


def test_slug_is_path_safe():
    assert slugify("  São Paulo / ../Grand Prix!! ") == "s-o-paulo-grand-prix"
    with pytest.raises(ValueError):
        slugify("../")


@pytest.mark.parametrize("bad", [(0, "X"), (100, "X"), (-1, "X")])
def test_race_id_rejects_bad_round(bad):
    with pytest.raises(ValueError):
        make_race_id(2024, *bad)


# ------------------------------------------------------------------ network


@pytest.mark.network
def test_network_ingest_2024_round_1(tmp_path, capsys):
    assert main(["--year", "2024", "--rounds", "1", "--data-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    with capsys.disabled():
        print("\n" + out.strip())
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
    assert (tmp_path / "openf1-cache" / "2024" / "sessions.json").exists()
