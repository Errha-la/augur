import io
import json
import math
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from augur import openf1
from augur.openf1 import (
    OpenF1Client,
    OpenF1Error,
    load_openf1_race,
    normalize_openf1,
    resolve_race_session,
    team_color,
)
from augur.schema import DEFAULT_TEAM_COLOR, LAP_COLUMNS

T0 = datetime(2024, 3, 2, 15, 0, tzinfo=timezone.utc)
SESSION = {"session_key": 9472, "meeting_key": 1229, "date_start": "2024-03-02T15:00:00Z",
           "location": "Sakhir", "is_cancelled": False}


def iso(seconds_after_start):
    return (T0 + timedelta(seconds=seconds_after_start)).isoformat()


def driver(number=1, code="VER", team="Red Bull Racing", colour="3671c6", name="Max VERSTAPPEN"):
    return {"driver_number": number, "name_acronym": code, "full_name": name,
            "team_name": team, "team_colour": colour}


def lap(number, start_s, duration, *, driver_number=1, pit_out=False):
    return {"driver_number": driver_number, "lap_number": number,
            "date_start": None if start_s is None else iso(start_s),
            "lap_duration": duration, "is_pit_out_lap": pit_out}


def stint(number, lap_start, lap_end, compound, age, driver_number=1):
    return {"driver_number": driver_number, "stint_number": number, "lap_start": lap_start,
            "lap_end": lap_end, "compound": compound, "tyre_age_at_start": age}


def rc(at_s, category, *, flag=None, scope=None, sector=None, message=""):
    return {"date": iso(at_s), "category": category, "flag": flag, "scope": scope,
            "sector": sector, "message": message}


def example_payloads():
    """Spec 'one lap row' example: VER laps 17 (in-lap) and 18 (out-lap)."""
    laps = [lap(17, 1700.0, 100.0), lap(18, 1800.0, 96.512, pit_out=True)]
    stints = [stint(1, 1, 17, "SOFT", 3), stint(2, 18, 37, "HARD", 0)]
    pits = [{"driver_number": 1, "lap_number": 17}]
    return SESSION, laps, stints, pits, [driver()], []


def row(df, lap_number, code="VER"):
    match = df[(df["driver"] == code) & (df["lap"] == lap_number)]
    assert len(match) == 1
    return match.iloc[0]


# ------------------------------------------------------------- normalization


def test_one_lap_row_example():
    laps, drivers = normalize_openf1(*example_payloads())
    assert tuple(laps.columns) == LAP_COLUMNS
    r = row(laps, 18)
    assert r["driver"] == "VER" and r["team"] == "Red Bull Racing"
    assert r["lap"] == 18
    assert r["lap_time_s"] == pytest.approx(96.512, abs=1e-9)
    assert r["session_time_s"] == pytest.approx(1896.512, abs=1e-9)
    assert r["stint"] == 2 and r["compound"] == "HARD" and r["tyre_life"] == 1
    assert bool(r["pit_in"]) is False and bool(r["pit_out"]) is True
    assert r["track_status"] == "1"
    assert bool(r["is_accurate"]) is False
    assert bool(row(laps, 17)["pit_in"]) is True
    assert row(laps, 17)["tyre_life"] == 3 + (17 - 1) + 1
    assert [(d.code, d.full_name, d.team, d.team_color, d.grid_position) for d in drivers] == [
        ("VER", "Max VERSTAPPEN", "Red Bull Racing", "#3671C6", None)
    ]


def test_dtypes():
    laps, _ = normalize_openf1(*example_payloads())
    assert laps["lap"].dtype == "int64"
    assert laps["lap_time_s"].dtype == "float64"
    assert laps["session_time_s"].dtype == "float64"
    assert str(laps["stint"].dtype) == "Int64"
    assert str(laps["tyre_life"].dtype) == "Int64"
    for col in ("pit_in", "pit_out", "is_accurate"):
        assert laps[col].dtype == "bool"
    for col in ("driver", "team", "compound", "track_status"):
        assert laps[col].dtype == "object"


def test_missing_lap_time():
    session, _, stints, pits, drivers, _ = example_payloads()
    laps, _ = normalize_openf1(session, [lap(5, 500.0, None)], stints, pits, drivers,
                               [rc(510, "SafetyCar", message="SAFETY CAR DEPLOYED")])
    r = row(laps, 5)
    assert math.isnan(r["lap_time_s"]) and math.isnan(r["session_time_s"])
    assert r["track_status"] is None
    assert bool(r["is_accurate"]) is False


def test_missing_date_start_gives_null_session_time_and_status():
    session, _, stints, pits, drivers, _ = example_payloads()
    laps, _ = normalize_openf1(session, [lap(5, None, 95.0)], stints, pits, drivers, [])
    r = row(laps, 5)
    assert r["lap_time_s"] == 95.0
    assert math.isnan(r["session_time_s"]) and r["track_status"] is None
    assert bool(r["is_accurate"]) is True


def test_missing_openf1_field_raises_keyerror():
    session, laps, stints, pits, drivers, race_control = example_payloads()
    for item in laps:
        del item["lap_duration"]
    with pytest.raises(KeyError, match="lap_duration"):
        normalize_openf1(session, laps, stints, pits, drivers, race_control)


@pytest.mark.parametrize(
    ("payload_index", "field"),
    [(2, "tyre_age_at_start"), (3, "lap_number"), (4, "team_colour"), (5, "sector")],
)
def test_missing_field_in_other_payloads(payload_index, field):
    payloads = list(example_payloads())
    payloads[5] = [rc(10, "Flag", flag="GREEN", scope="Track")]
    for item in payloads[payload_index]:
        del item[field]
    with pytest.raises(KeyError, match=field):
        normalize_openf1(*payloads)


def test_lap_without_driver_row_raises():
    session, laps, stints, pits, drivers, race_control = example_payloads()
    laps.append(lap(3, 300.0, 95.0, driver_number=44))
    with pytest.raises(ValueError, match="driver_number.*44"):
        normalize_openf1(session, laps, stints, pits, drivers, race_control)


def test_lap_one_is_not_accurate_and_unknown_compound_is_null():
    session, _, _, _, drivers, _ = example_payloads()
    laps, _ = normalize_openf1(session, [lap(1, 0.0, 99.0), lap(2, 99.0, 95.0), lap(40, 4000, 95.0)],
                               [stint(1, 1, 2, "UNKNOWN", None)], [], drivers, [])
    assert bool(row(laps, 1)["is_accurate"]) is False
    assert bool(row(laps, 2)["is_accurate"]) is True
    assert row(laps, 2)["compound"] is None and row(laps, 2)["stint"] == 1
    assert pd_isna(row(laps, 2)["tyre_life"])
    # no stint covers lap 40
    assert pd_isna(row(laps, 40)["stint"]) and row(laps, 40)["compound"] is None


def pd_isna(value):
    import pandas as pd

    return bool(pd.isna(value))


def test_duplicate_lap_rejected():
    session, laps, stints, pits, drivers, race_control = example_payloads()
    laps.append(dict(laps[0]))
    with pytest.raises(ValueError, match="duplicate lap"):
        normalize_openf1(session, laps, stints, pits, drivers, race_control)


@pytest.mark.parametrize("bad_laps", [{"lap_number": 1}, [1, 2], [{"driver_number": "1", "lap_number": 1,
                                       "date_start": None, "lap_duration": None, "is_pit_out_lap": None}]])
def test_malformed_payload_fails_loudly(bad_laps):
    session, _, stints, pits, drivers, race_control = example_payloads()
    with pytest.raises((TypeError, ValueError)):
        normalize_openf1(session, bad_laps, stints, pits, drivers, race_control)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("3671c6", "#3671C6"), ("#E8002D", "#E8002D"), ("", DEFAULT_TEAM_COLOR),
     (None, DEFAULT_TEAM_COLOR), ("zzzzzz", DEFAULT_TEAM_COLOR), ("12345", DEFAULT_TEAM_COLOR)],
)
def test_team_color(value, expected):
    assert team_color(value) == expected


# --------------------------------------------------------------- track status

YELLOW_S2 = [rc(150, "Flag", flag="YELLOW", scope="Sector", sector=2),
             rc(160, "Flag", flag="CLEAR", scope="Sector", sector=2)]


@pytest.mark.parametrize(
    ("messages", "window", "expected"),
    [
        ([], (100, 196), "1"),
        (YELLOW_S2, (100, 196), "2"),
        (YELLOW_S2, (200, 296), "1"),
        ([rc(150, "SafetyCar", message="VIRTUAL SAFETY CAR DEPLOYED"),
          rc(400, "SafetyCar", message="VIRTUAL SAFETY CAR ENDING")], (200, 296), "6"),
        ([rc(150, "SafetyCar", message="SAFETY CAR DEPLOYED"),
          rc(500, "Flag", flag="GREEN", scope="Track")], (200, 296), "4"),
        ([rc(120, "Flag", flag="YELLOW", scope="Sector", sector=1),
          rc(150, "SafetyCar", message="SAFETY CAR DEPLOYED")], (100, 196), "4"),
        ([rc(150, "Flag", flag="RED", scope="Track"),
          rc(900, "Flag", flag="GREEN", scope="Track")], (100, 196), "5"),
    ],
    ids=["none", "yellow-in-window", "yellow-cleared-before", "vsc", "sc", "yellow-then-sc", "red"],
)
def test_status_per_lap_window(messages, window, expected):
    start, end = window
    session, _, _, _, drivers, _ = example_payloads()
    laps, _ = normalize_openf1(session, [lap(2, float(start), float(end - start))], [], [], drivers, messages)
    assert row(laps, 2)["track_status"] == expected


def test_status_track_clear_ends_everything_but_vsc_needs_ending():
    msgs = [rc(10, "Flag", flag="DOUBLE YELLOW", scope="Sector", sector=3),
            rc(20, "SafetyCar", message="SAFETY CAR DEPLOYED"),
            rc(30, "Flag", flag="CLEAR", scope="Track")]
    session, _, _, _, drivers, _ = example_payloads()
    laps, _ = normalize_openf1(session, [lap(2, 100.0, 50.0)], [], [], drivers, msgs)
    assert row(laps, 2)["track_status"] == "1"


# ------------------------------------------------------------ round resolution


def test_round_numbers_skip_cancelled_races():
    sessions = [
        {**SESSION, "session_key": 3, "date_start": "2024-03-20T15:00:00+00:00"},  # C
        {**SESSION, "session_key": 1, "date_start": "2024-03-02T15:00:00+00:00"},  # A
        {**SESSION, "session_key": 2, "date_start": "2024-03-10T15:00:00+00:00", "is_cancelled": True},  # B
    ]
    assert resolve_race_session(sessions, 1)["session_key"] == 1
    assert resolve_race_session(sessions, 2)["session_key"] == 3
    with pytest.raises(LookupError, match="^no race session for round 3$"):
        resolve_race_session(sessions, 3)


# ------------------------------------------------------------------ HTTP client


class FakeResponse(io.BytesIO):
    def __init__(self, payload, status=200):
        super().__init__(json.dumps(payload).encode())
        self.status = status


class FakeOpener:
    """Returns queued responses per endpoint; ints are HTTP error codes."""

    def __init__(self, routes):
        self.routes = {k: list(v) for k, v in routes.items()}
        self.urls = []

    def __call__(self, request, timeout):
        assert timeout == 60
        url = request.full_url
        assert url.startswith("https://api.openf1.org/v1/")
        self.urls.append(url)
        endpoint = url.removeprefix("https://api.openf1.org/v1/").split("?")[0]
        item = self.routes[endpoint].pop(0) if len(self.routes[endpoint]) > 1 else self.routes[endpoint][0]
        if isinstance(item, int):
            raise urllib.error.HTTPError(url, item, "error", {}, io.BytesIO(b"{}"))
        return FakeResponse(item)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(tmp_path, routes):
    opener, clock = FakeOpener(routes), FakeClock()
    client = OpenF1Client(tmp_path / "openf1-cache", opener=opener, sleep=clock.sleep, clock=clock.clock)
    return client, opener, clock


def test_retry_after_429_succeeds(tmp_path):
    client, opener, clock = make_client(tmp_path, {"drivers": [429, 503, [driver()]]})
    assert client.session_list("drivers", 9472) == [driver()]
    assert len(opener.urls) == 3
    assert [s for s in clock.sleeps if s >= 2] == [2.0, 4.0]


def test_gives_up_after_three_retries(tmp_path):
    client, opener, clock = make_client(tmp_path, {"laps": [429]})
    with pytest.raises(OpenF1Error, match="HTTP 429 after 3 retries"):
        client.session_list("laps", 9472)
    assert len(opener.urls) == 4
    assert [s for s in clock.sleeps if s >= 2] == [2.0, 4.0, 8.0]
    assert not (tmp_path / "openf1-cache" / "9472" / "laps.json").exists()


def test_404_is_not_retried_or_cached(tmp_path):
    client, opener, _ = make_client(tmp_path, {"pit": [404]})
    with pytest.raises(OpenF1Error, match="HTTP 404"):
        client.session_list("pit", 9472)
    assert len(opener.urls) == 1
    assert not (tmp_path / "openf1-cache" / "9472").exists()


def test_non_list_response_rejected(tmp_path):
    client, _, _ = make_client(tmp_path, {"laps": [{"detail": "nope"}]})
    with pytest.raises(OpenF1Error, match="expected a list"):
        client.session_list("laps", 9472)


def test_throttle_at_most_three_per_second(tmp_path):
    client, opener, clock = make_client(tmp_path, {e: [[]] for e in openf1.SESSION_ENDPOINTS})
    starts = []
    real = opener.__call__

    def timed(request, timeout):
        starts.append(clock.now)
        return real(request, timeout)

    client._opener = timed
    for endpoint in openf1.SESSION_ENDPOINTS:
        client.session_list(endpoint, 9472)
    assert len(starts) == 5
    for i in range(len(starts) - 3):
        assert starts[i + 3] - starts[i] >= 1.0 - 1e-9


def test_client_rejects_unknown_endpoints(tmp_path):
    client, _, _ = make_client(tmp_path, {})
    for bad in ("session_result", "starting_grid", "../laps"):
        with pytest.raises(ValueError):
            client.session_list(bad, 9472)
    with pytest.raises(ValueError):
        client.session_list("laps", "9472&x=1")


def race_routes():
    return {
        "sessions": [[{**SESSION, "session_name": "Race"}]],
        "meetings": [[{"meeting_key": 1229, "meeting_name": "Bahrain Grand Prix"}]],
        "drivers": [[driver()]],
        "laps": [[lap(1, 0.0, 99.0)]],
        "stints": [[stint(1, 1, 17, "SOFT", 3)]],
        "pit": [[]],
        "race_control": [[]],
    }


def test_load_race_requests_and_cache(tmp_path):
    client, opener, _ = make_client(tmp_path, race_routes())
    payload = load_openf1_race(2024, 1, tmp_path, client=client)
    assert payload.meeting_name == "Bahrain Grand Prix"
    assert payload.session["session_key"] == 9472
    assert sorted(u.split("?")[0].rsplit("/", 1)[1] for u in opener.urls) == sorted(
        ["sessions", "meetings", "drivers", "laps", "stints", "pit", "race_control"]
    )
    assert "year=2024&session_name=Race" in opener.urls[0]
    assert all("session_result" not in u and "starting_grid" not in u for u in opener.urls)
    cache = tmp_path / "openf1-cache"
    assert (cache / "2024" / "sessions.json").exists() and (cache / "2024" / "meetings.json").exists()
    assert sorted(p.name for p in (cache / "9472").iterdir()) == sorted(
        f"{e}.json" for e in ("drivers", "laps", "stints", "pit", "race_control")
    )

    # second load: everything from cache, no HTTP calls
    client2, opener2, _ = make_client(tmp_path, {})
    again = load_openf1_race(2024, 1, tmp_path, client=client2)
    assert opener2.urls == [] and client2.requests == 0
    assert again == payload
