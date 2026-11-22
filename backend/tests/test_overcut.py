"""overcut_window detector and template (polish 1.1)."""

from __future__ import annotations

import re
from dataclasses import replace

import pytest
from synthetic import write_synthetic_race

from augur.events.analysis import explain
from augur.events.detectors import CarStatus, DetectorState, detect_overcut
from augur.events.engine import EventEngine
from augur.feed import ReplayFeed
from augur.models.baseline import BaselineModel
from augur.replay import ReplayStore

# Order after lap 19: PIA leads, NOR is right behind it.
AHEAD = CarStatus("PIA", 1, 19, 1900.0, 1, "MEDIUM", 19, False, 0.09)
NOR = CarStatus("NOR", 2, 19, 1902.1, 1, "HARD", 19, False, 0.03)


def run(gap: float, deg: float | None, *, pit_in=("PIA",), state=None, lap=20):
    chaser = replace(NOR, session_time_s=AHEAD.session_time_s + gap)
    return detect_overcut(lap, [chaser, AHEAD], set(pit_in), {"NOR": deg}, state or DetectorState())


@pytest.mark.parametrize(
    ("gap", "deg", "fires"),
    [(2.1, 0.03, True), (3.4, 0.03, False), (2.1, 0.08, False)],
)
def test_conditions_table(gap, deg, fires):
    """Scenario: Overcut cases (Example: conditions)."""
    events = run(gap, deg)
    if not fires:
        assert events == []
        return
    (e,) = events
    assert e["type"] == "overcut_window" and e["drivers"] == ["NOR", "PIA"] and e["severity"] == 55
    assert e["lap"] == 20
    assert e["evidence"] == {
        "driver": "NOR",
        "ahead": "PIA",
        "gap_s": 2.1,
        "deg_s_per_lap": 0.03,
        "compound": "HARD",
        "tyre_life": 19,
        "ahead_compound": "MEDIUM",
    }


def test_boundaries_and_missing_values():
    assert run(2.999, 0.049) != []
    assert run(3.0, 0.03) == []  # less than 3.0 s
    assert run(2.1, 0.05) == []  # below 0.05
    assert run(2.1, None) == []  # no degradation fit yet
    assert run(-0.5, 0.03) == []  # not behind


def test_needs_the_car_ahead_to_pit_and_driver_to_stay_out():
    assert run(2.1, 0.03, pit_in=()) == []
    assert run(2.1, 0.03, pit_in=("NOR",)) == []
    assert run(2.1, 0.03, pit_in=("PIA", "NOR")) == []  # both stop: nobody stays out


def test_directly_behind_and_same_lap_count_only():
    lec = CarStatus("LEC", 2, 19, 1901.0, 1, "HARD", 10, False, 0.02)
    behind_lec = replace(NOR, position=3)
    assert [e["drivers"] for e in detect_overcut(20, [AHEAD, lec, behind_lec], {"PIA"}, {"NOR": 0.03, "LEC": 0.02}, DetectorState())] == [["LEC", "PIA"]]
    lapped = replace(NOR, laps_completed=18)
    assert detect_overcut(20, [AHEAD, lapped], {"PIA"}, {"NOR": 0.03}, DetectorState()) == []


def test_once_per_pair_per_stop():
    state = DetectorState()
    assert len(run(2.1, 0.03, state=state)) == 1
    assert run(2.1, 0.03, state=state) == []  # same stop seen again
    assert len(run(2.1, 0.03, state=state, lap=40)) == 1  # a later stop re-arms the pair


def test_template_is_conditional_and_names_strategy():
    (e,) = run(2.1, 0.03)
    e = {**e, "evidence": {**e["evidence"], "strategy": {"name": "stop", "pit_lap": 24, "win_probability": 0.71}}}
    title, analysis = explain(e)
    assert title == "Overcut window: NOR on PIA"
    assert analysis["what"] == "PIA pitted on lap 20 with NOR 2.1 s behind on lap 19."
    assert "0.030 s per lap" in analysis["why"] and "HARD" in analysis["why"]
    assert analysis["next"] == "Pitting on lap 24 is NOR's fastest option in 71% of simulations, which would put pressure on PIA."
    text = " ".join(analysis.values())
    assert not re.search(r"\b(should|must|will)\b", text, re.IGNORECASE)


def test_template_with_falling_lap_times():
    (e,) = run(2.8, -0.063)
    _, analysis = explain(e)
    assert "not losing time yet (lap times falling 0.063 s per lap)" in analysis["why"]
    assert "-0.063" not in analysis["why"]


def test_engine_emits_overcut_with_strategy(tmp_path):
    """The engine wires the detector in and adds the driver's best strategy."""
    data = tmp_path / "data"
    race = write_synthetic_race(data, 2098, 1, 1)
    engine = EventEngine(ReplayFeed(race, ReplayStore(data)), BaselineModel())
    events = [e for lap in range(1, engine.feed.total_laps + 1) for e in engine.step(lap)]
    for e in (e for e in events if e["type"] == "overcut_window"):
        assert "strategy" in e["evidence"] and e["severity"] == 55
        assert e["analysis"]["next"]
