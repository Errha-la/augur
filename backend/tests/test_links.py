"""Number links in events (commentary-chart-links 1.2)."""

from __future__ import annotations

import pytest

from augur.events.links import event_links


def undercut(**over) -> dict:
    event = {
        "id": "r:20:undercut_window:NOR-PIA", "lap": 20, "type": "undercut_window", "drivers": ["NOR", "PIA"],
        "evidence": {"chaser": "NOR", "ahead": "PIA", "gap_s": 1.84, "ahead_tyre_life": 14,
                     "strategy": {"pit_lap": 22, "win_probability": 0.62}},
        "analysis": {"what": "NOR is 1.8 s behind PIA on lap 20.", "why": "Old tyres.", "next": "A stop could pay."},
        "commentary": "PIA's tyres are 14 laps old, and NOR wins 62% of runs",
    }
    event.update(over)
    return event


# Scenario: Gap and tyre age links / Example: undercut at lap 20
def test_gap_and_tyre_age_links():
    links = event_links(undercut())
    assert links["what"] == [{"start": 7, "end": 10, "field": "gap_s", "chart": "trace", "drivers": ["NOR", "PIA"]}]
    assert links["commentary"] == [
        {"start": 16, "end": 18, "field": "ahead_tyre_life", "chart": "stints", "drivers": ["PIA"]},
        {"start": 42, "end": 45, "field": "strategy.win_probability", "chart": "pitwindow", "drivers": ["NOR"]},
    ]
    assert links["why"] == [] and links["next"] == []


# Scenario: Event lap is not linked
def test_event_lap_is_not_linked():
    event = {"lap": 20, "type": "pace_drop", "drivers": ["NOR"], "evidence": {"driver": "NOR", "tyre_life": 20},
             "analysis": {"what": "NOR on 20-lap-old tyres", "why": "", "next": ""}, "commentary": None}
    assert event_links(event)["what"] == []


# Scenario: Code-point offsets in Chinese commentary
def test_code_point_offsets_in_chinese_commentary():
    links = event_links(undercut(commentary="NOR 落後 PIA 1.8 秒"))
    assert [(l["start"], l["end"], l["field"]) for l in links["commentary"]] == [(11, 14, "gap_s")]


def test_null_commentary_gives_empty_list():
    links = event_links(undercut(commentary=None))
    assert set(links) == {"what", "why", "next", "commentary"} and links["commentary"] == []


def test_unmatched_number_unlinked_and_trailing_space_not_in_span():
    links = event_links(undercut(commentary="about 3 s, then 1.8 s"))
    assert [(l["start"], l["end"]) for l in links["commentary"]] == [(16, 19)]


def test_first_field_in_table_order_wins():
    event = {"lap": 30, "drivers": ["VER"], "evidence": {"driver": "VER", "tyre_life": 12, "stint": 12},
             "analysis": {"what": "12", "why": "", "next": ""}}
    assert event_links(event)["what"][0]["field"] == "tyre_life"


def test_missing_driver_left_out_and_null_field_skipped():
    event = {"lap": 30, "drivers": ["VER"],
             "evidence": {"gap_s": 2.5, "ahead": None, "chaser": "VER", "tyre_life": None, "cliff": True},
             "analysis": {"what": "2.5 and 7 and 1", "why": "", "next": ""}}
    assert event_links(event)["what"] == [
        {"start": 0, "end": 3, "field": "gap_s", "chart": "trace", "drivers": ["VER"]}
    ]


# One case per field-table row: (evidence, text, field, chart, drivers).
ROWS = [
    ({"driver": "HAM", "deg_s_per_lap": 0.084}, "0.084", "deg_s_per_lap", "degradation", ["HAM"]),
    ({"driver": "HAM", "deg_laps": 9}, "9", "deg_laps", "degradation", ["HAM"]),
    ({"chaser": "HAM", "ahead": "RUS", "ahead_deg_s_per_lap": 0.121}, "0.121", "ahead_deg_s_per_lap",
     "degradation", ["RUS"]),
    ({"driver": "HAM", "lap_time_s": 88.412}, "88.412", "lap_time_s", "laptimes", ["HAM"]),
    ({"driver": "HAM", "predicted_s": 86.9}, "86.900", "predicted_s", "laptimes", ["HAM"]),
    ({"driver": "HAM", "slower_s": 1.51}, "1.5", "slower_s", "laptimes", ["HAM"]),
    ({"driver": "HAM", "ahead": "RUS", "gap_s": 3.26}, "3.3", "gap_s", "trace", ["HAM", "RUS"]),
    ({"driver": "HAM", "tyre_life": 17}, "17", "tyre_life", "stints", ["HAM"]),
    ({"driver": "HAM", "stint": 2}, "2", "stint", "stints", ["HAM"]),
    ({"chaser": "HAM", "ahead": "RUS", "ahead_tyre_life": 19}, "19", "ahead_tyre_life", "stints", ["RUS"]),
    ({"chaser": "HAM", "ahead": "RUS", "ahead_stint": 3}, "3", "ahead_stint", "stints", ["RUS"]),
    ({"chaser": "HAM", "ahead": "RUS", "chaser_tyre_life": 6}, "6", "chaser_tyre_life", "stints", ["HAM"]),
    ({"driver": "HAM", "strategy": {"pit_lap": 41, "win_probability": 0.3}}, "41", "strategy.pit_lap",
     "pitwindow", ["HAM"]),
    ({"driver": "HAM", "strategy": {"pit_lap": None, "win_probability": 0.47}}, "47%",
     "strategy.win_probability", "pitwindow", ["HAM"]),
    ({"driver": "HAM", "from_position": 8}, "P8", "from_position", "positions", ["HAM"]),
    ({"driver": "HAM", "to_position": 5}, "P5", "to_position", "positions", ["HAM"]),
    ({"driver": "HAM", "places": -3}, "3", "places", "positions", ["HAM"]),
    ({"driver": "HAM", "laps_remaining": 24}, "24", "laps_remaining", "positions", ["HAM"]),
]


@pytest.mark.parametrize(("evidence", "text", "field", "chart", "drivers"), ROWS, ids=[r[2] for r in ROWS])
def test_field_table_row(evidence, text, field, chart, drivers):
    event = {"lap": 35, "drivers": ["HAM", "RUS"], "evidence": evidence,
             "analysis": {"what": text, "why": "", "next": ""}, "commentary": None}
    (link,) = event_links(event)["what"]
    assert (link["field"], link["chart"], link["drivers"]) == (field, chart, drivers)
    assert text[link["start"]:link["end"]] == text.lstrip("P")
