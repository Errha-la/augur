import re

import pytest
from synthetic import write_synthetic_race

from augur.events.analysis import explain, strategy_outlook
from augur.events.engine import EventEngine
from augur.feed import ReplayFeed
from augur.models.baseline import BaselineModel
from augur.replay import ReplayStore

IMPERATIVES = {"Pit", "Stay", "Push", "Box"}

EXAMPLES = {
    "pace_drop": {
        "driver": "HAM", "lap_time_s": 96.6, "predicted_s": 95.0, "slower_s": 1.6,
        "compound": "MEDIUM", "tyre_life": 14,
    },
    "degradation_warning": {
        "driver": "VER", "stint": 1, "compound": "SOFT", "tyre_life": 15, "deg_s_per_lap": 0.12,
        "deg_laps": 9, "cliff": False,
        "strategy": {"name": "pit on lap 22", "pit_lap": 22, "mean_s": 3000.0, "win_probability": 0.55},
    },
    "undercut_window": {
        "chaser": "NOR", "ahead": "PIA", "gap_s": 1.8, "ahead_tyre_life": 18, "ahead_compound": "MEDIUM",
        "ahead_stint": 1, "ahead_deg_s_per_lap": 0.08, "chaser_tyre_life": 18, "chaser_compound": "MEDIUM",
        "strategy": {"name": "pit on lap 21", "pit_lap": 21, "mean_s": 3000.0, "win_probability": 0.62},
    },
    "position_change": {
        "driver": "LEC", "previous_leader": "VER", "from_position": 2, "to_position": 1, "places": 1,
        "leader_change": True, "laps_remaining": 27, "pit_drivers": ["VER"],
    },
}


def first_word(text: str) -> str:
    return re.split(r"[\s,.;:]+", text.strip())[0]


def test_outlook_wording_example():
    text = strategy_outlook(
        "NOR", {"name": "pit on lap 21", "pit_lap": 21, "win_probability": 0.62}, rival="PIA"
    )
    assert text == "Pitting on lap 21 is NOR's fastest option in 62% of simulations, which would put pressure on PIA."
    assert "Pit now" not in text


def test_undercut_analysis_text():
    title, a = explain({"lap": 20, "type": "undercut_window", "evidence": EXAMPLES["undercut_window"]})
    assert "NOR" in a["what"] and "PIA" in a["what"] and "1.8 s" in a["what"]
    assert "PIA" in a["why"] and "18 laps old" in a["why"] and "0.080 s per lap" in a["why"]
    assert a["next"] == (
        "Pitting on lap 21 is NOR's fastest option in 62% of simulations, which would put pressure on PIA."
    )
    assert title == "Undercut window: NOR on PIA"


@pytest.mark.parametrize("type_", sorted(EXAMPLES))
def test_every_type_has_three_sentences_and_is_deterministic(type_):
    event = {"lap": 20, "type": type_, "evidence": EXAMPLES[type_]}
    first, second = explain(event), explain(event)
    assert first == second
    title, a = first
    assert title
    for key in ("what", "why", "next"):
        assert a[key].strip() and a[key].endswith(".")
    assert first_word(a["next"]) not in IMPERATIVES


def test_no_further_stop_outlook_is_not_imperative():
    text = strategy_outlook("VER", {"name": "no further stop", "pit_lap": None, "win_probability": 0.7})
    assert first_word(text) not in IMPERATIVES
    assert "70% of simulations" in text


def test_engine_events_have_analysis_and_no_imperatives(tmp_path):
    data = tmp_path / "data"
    race = write_synthetic_race(data, 2098, 1, 1)
    feed = ReplayFeed(race, ReplayStore(data))
    runs = []
    for _ in range(2):
        engine = EventEngine(feed, BaselineModel())
        runs.append([e for lap in range(1, 31) for e in engine.step(lap)])
    assert runs[0] == runs[1]
    for e in runs[0]:
        assert set(e) == {"id", "lap", "type", "drivers", "severity", "title", "analysis", "evidence"}
        assert all(e["analysis"][k] for k in ("what", "why", "next"))
        assert first_word(e["analysis"]["next"]) not in IMPERATIVES
        if e["type"] in ("degradation_warning", "undercut_window"):
            assert "strategy" in e["evidence"]
