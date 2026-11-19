import pandas as pd
import pytest
from synthetic import write_synthetic_race

from augur.events.detectors import (
    DetectorState,
    LapObservation,
    detect_degradation,
    detect_pace_drop,
    detect_position_change,
)
from augur.events.engine import EventEngine, OutOfOrderStep
from augur.feed import ReplayFeed
from augur.models.baseline import BaselineModel
from augur.replay import ReplayStore


@pytest.fixture
def engine(tmp_path):
    data = tmp_path / "data"
    race = write_synthetic_race(data, 2098, 1, 1)
    return EventEngine(ReplayFeed(race, ReplayStore(data)), BaselineModel())


def test_out_of_order_step(engine):
    engine.step(1)
    engine.step(2)
    engine.step(3)
    with pytest.raises(OutOfOrderStep, match="expected lap 4"):
        engine.step(5)


def test_first_step_must_be_lap_one(engine):
    with pytest.raises(OutOfOrderStep, match="expected lap 1"):
        engine.step(2)


def test_engine_runs_whole_race_with_ids(engine):
    events = [e for lap in range(1, 31) for e in engine.step(lap)]
    assert events, "synthetic race should produce events"
    for e in events:
        assert e["id"] == f"{engine.feed.race_id}:{e['lap']}:{e['type']}:{'-'.join(e['drivers'])}"
        assert 0 <= e["severity"] <= 100
    assert len({e["id"] for e in events}) == len(events)
    assert any(e["type"] == "position_change" for e in events)  # pit stops reshuffle the order


def test_engine_handles_missing_tyre_life_and_compound(tmp_path):
    # Real OpenF1 data has laps without stint data (tyre_life <NA>, compound None).
    from conftest import write_race
    from synthetic import SYN_DRIVER_ROWS, synthetic_race_laps

    laps = synthetic_race_laps(1)
    gap = (laps["driver"] == "CCC") & laps["lap"].between(20, 22)
    laps.loc[gap, "tyre_life"] = pd.NA
    laps.loc[gap, "compound"] = None
    laps.loc[gap, "stint"] = pd.NA
    data = tmp_path / "data"
    race = "2098-05-gap-grand-prix"
    write_race(data, race, laps, year=2098, round_=5, event_name="Gap", total_laps=30, drivers=SYN_DRIVER_ROWS)
    engine = EventEngine(ReplayFeed(race, ReplayStore(data)), BaselineModel())
    for lap in range(1, 31):
        engine.step(lap)


def test_pace_drop_example_severity_48():
    state = DetectorState()
    obs = [LapObservation("HAM", 96.6, 95.0, True)]
    events = detect_pace_drop(20, obs, state)
    assert len(events) == 1
    assert events[0]["type"] == "pace_drop" and events[0]["drivers"] == ["HAM"]
    assert events[0]["severity"] == 48


def test_pace_drop_rules():
    state = DetectorState()
    assert detect_pace_drop(5, [LapObservation("HAM", 96.0, 95.0, True)], state) == []  # exactly 1.0 s
    assert detect_pace_drop(5, [LapObservation("HAM", 99.0, 95.0, False)], state) == []  # not clean
    assert len(detect_pace_drop(6, [LapObservation("HAM", 99.0, 95.0, True)], state)) == 1
    assert detect_pace_drop(8, [LapObservation("HAM", 99.0, 95.0, True)], state) == []  # cooldown
    assert len(detect_pace_drop(9, [LapObservation("HAM", 99.0, 95.0, True)], state)) == 1
    assert detect_pace_drop(9, [LapObservation("VER", 99.0, None, True)], state) == []


@pytest.mark.parametrize(
    "lap, prev, now, expected",
    [
        (10, {"A": 1, "B": 2, "C": 3}, {"A": 1, "C": 2, "B": 3}, []),  # gains 1 place
        (10, {"A": 1, "B": 2, "C": 3, "D": 4}, {"A": 1, "C": 2, "D": 3, "B": 4},
         [(["B"], 40.0)]),  # loses 2 places
        (10, {"A": 1, "B": 2, "C": 3}, {"B": 1, "A": 2, "C": 3}, [(["B", "A"], 90.0)]),  # leader change
    ],
)
def test_position_change_thresholds(lap, prev, now, expected):
    state = DetectorState(prev_positions=prev)
    events = detect_position_change(lap, now, state, total_laps=57)
    assert [(e["drivers"], e["severity"]) for e in events] == expected


def test_no_position_change_on_own_pit_lap():
    # driver loses 3 places on their own pit-in lap -> none
    prev = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
    now = {"A": 1, "C": 2, "D": 3, "E": 4, "B": 5}
    state = DetectorState(prev_positions=prev)
    assert detect_position_change(10, now, state, 57, pitted=["B"]) == []
    assert state.prev_positions == now  # memory still advances


def test_position_change_when_other_cars_pit():
    # driver gains 2 places while two other cars pit -> position_change, severity 40
    prev = {"A": 1, "B": 2, "C": 3, "D": 4}
    now = {"A": 1, "D": 2, "B": 3, "C": 4}
    events = detect_position_change(10, now, DetectorState(prev_positions=prev), 57, pitted=["B", "C"])
    assert [(e["drivers"], e["severity"]) for e in events] == [(["D"], 40.0)]


def test_leader_change_skipped_when_new_leader_pitted():
    prev = {"A": 1, "B": 2, "C": 3}
    now = {"B": 1, "A": 2, "C": 3}
    assert detect_position_change(10, now, DetectorState(prev_positions=prev), 57, pitted=["B"]) == []


def test_no_position_change_on_lap_one():
    state = DetectorState(prev_positions={"A": 1, "B": 2, "C": 3})
    assert detect_position_change(1, {"C": 1, "B": 2, "A": 3}, state, 57) == []


def _deg(slope, laps, stint=1, cliff=False):
    return {"VER": {"stint": stint, "compound": "MEDIUM", "tyre_life": laps + 2,
                    "deg_s_per_lap": slope, "deg_laps": laps, "cliff": cliff}}


def test_degradation_warning_fires_once_per_stint():
    state = DetectorState()
    events = []
    for lap in range(18, 26):
        events += detect_degradation(lap, _deg(0.12, lap - 12), state)
    non_cliff = [e for e in events if not e["evidence"]["cliff"]]
    assert len(non_cliff) == 1
    assert non_cliff[0]["lap"] == 20  # first lap with 8 clean laps
    assert non_cliff[0]["severity"] == 60.0
    # a new stint can warn again; a cliff can fire once more
    assert len(detect_degradation(40, _deg(0.12, 8, stint=2), state)) == 1
    assert detect_degradation(41, _deg(0.12, 9, stint=2), state) == []
    cliff = detect_degradation(42, _deg(0.12, 10, stint=2, cliff=True), state)
    assert [e["severity"] for e in cliff] == [80.0]
    assert detect_degradation(43, _deg(0.12, 11, stint=2, cliff=True), state) == []


def test_too_few_clean_laps_for_degradation_warning():
    # slope 0.30 s per lap over 7 clean laps, no cliff -> none
    assert detect_degradation(15, _deg(0.30, 7), DetectorState()) == []


def test_cliff_fires_below_eight_clean_laps():
    events = detect_degradation(15, _deg(0.05, 6, cliff=True), DetectorState())
    assert [e["severity"] for e in events] == [80.0]


def test_degradation_below_thresholds_is_silent():
    state = DetectorState()
    assert detect_degradation(10, _deg(0.09, 10), state) == []
    assert detect_degradation(10, _deg(0.2, 4), state) == []
    assert detect_degradation(10, _deg(None, 3), state) == []
