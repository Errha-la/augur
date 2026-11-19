import pandas as pd
from fastapi.testclient import TestClient

from augur import catalog
from augur.api import create_app

FORBIDDEN_KEYS = {"final_position", "classification", "points", "status", "position_final"}


def keys_in(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys_in(v)


def test_state_unaffected_by_future_laps(fixture_race):
    client = TestClient(create_app(fixture_race.data_dir))
    rid = fixture_race.race_id
    urls = [f"/api/races/{rid}/state?lap=3", f"/api/races/{rid}/laps?lap=3"]
    before = [client.get(u) for u in urls]
    assert all(r.status_code == 200 for r in before)

    path = catalog.laps_path(fixture_race.data_dir, rid)
    laps = pd.read_parquet(path)
    future = laps["lap"] > 3
    assert future.any()
    laps.loc[future, "lap_time_s"] = 1.0
    laps.loc[future, "session_time_s"] = 1.0  # would reorder everything if leaked
    laps.loc[future, "compound"] = "WET"
    laps.loc[future, "stint"] = 9
    laps.loc[future, "tyre_life"] = 99
    laps.loc[future, "track_status"] = "5"
    laps.loc[future, "pit_in"] = True
    laps.to_parquet(path, index=False)

    # Sanity: the rewrite is visible at a lap that includes the altered rows.
    assert "WET" in client.get(f"/api/races/{rid}/laps?lap=5").text

    after = [client.get(u) for u in urls]
    for b, a in zip(before, after):
        assert a.status_code == 200
        assert a.content == b.content


def test_no_final_classification_fields(fixture_race):
    client = TestClient(create_app(fixture_race.data_dir))
    rid = fixture_race.race_id
    payloads = [
        client.get("/api/races").json(),
        client.get(f"/api/races/{rid}/state?lap=5").json(),
        client.get(f"/api/races/{rid}/laps?lap=5").json(),
    ]
    for p in payloads:
        assert not FORBIDDEN_KEYS & set(keys_in(p))
