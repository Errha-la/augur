from dataclasses import replace

import pytest

from augur.events.detectors import CarStatus, DetectorState, detect_undercut

AHEAD = CarStatus("PIA", 1, 20, 2000.0, 1, "MEDIUM", 18, False, 0.08)
CHASER = CarStatus("NOR", 2, 20, 2001.8, 1, "MEDIUM", 18, False, 0.05)


def test_fires_once_for_two_driver_fixture():
    state = DetectorState()
    events = detect_undercut(20, [CHASER, AHEAD], state)
    assert len(events) == 1
    e = events[0]
    assert e["type"] == "undercut_window" and e["drivers"] == ["NOR", "PIA"] and e["severity"] == 60
    assert e["evidence"]["gap_s"] == 1.8 and e["evidence"]["ahead_tyre_life"] == 18
    # same pair, same stint of the car ahead: no repeat
    later_ahead = replace(AHEAD, laps_completed=21, session_time_s=2092.0, tyre_life=19)
    later_chaser = replace(CHASER, laps_completed=21, session_time_s=2093.0, tyre_life=19)
    assert detect_undercut(21, [later_ahead, later_chaser], state) == []
    # a new stint of the car ahead re-arms the pair
    new_stint = replace(later_ahead, stint=2, tyre_life=13)
    assert len(detect_undercut(35, [new_stint, later_chaser], state)) == 1


@pytest.mark.parametrize(
    "ahead, chaser",
    [
        (AHEAD, replace(CHASER, session_time_s=2002.6)),  # gap 2.6 s > 2.5 s
        (replace(AHEAD, tyre_life=11), CHASER),  # car ahead tyres too new
        (replace(AHEAD, pitted_recently=True), CHASER),  # car ahead pitted in last 3 laps
        (AHEAD, replace(CHASER, pitted_recently=True)),  # chaser pitted in last 3 laps
        (AHEAD, replace(CHASER, laps_completed=19)),  # not on the same lap count
        (AHEAD, replace(CHASER, position=3)),  # not directly behind (a car in between)
    ],
)
def test_single_failing_condition_fires_nothing(ahead, chaser):
    cars = [ahead, chaser]
    if chaser.position == 3:
        cars.append(CarStatus("LEC", 2, 20, 2001.0, 1, "HARD", 5, True, None))
    assert [e for e in detect_undercut(20, cars, DetectorState()) if e["drivers"] == ["NOR", "PIA"]] == []


def test_gap_exactly_2_5_fires():
    assert len(detect_undercut(20, [AHEAD, replace(CHASER, session_time_s=2002.5)], DetectorState())) == 1
