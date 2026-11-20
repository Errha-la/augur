"""Grounding check for generated commentary (llm-commentary 1.3)."""

from __future__ import annotations

import pytest

from augur.narration.grounding import Grounding, check_grounding

# Scenario: Grounding cases. Template text carries no numbers so only the
# evidence can ground a number, as in the spec table.
EVENT = {
    "id": "r:20:undercut_window:NOR-PIA",
    "lap": 20,
    "drivers": ["NOR", "PIA"],
    "evidence": {"gap_s": 1.84, "win_probability": 0.62, "tyre_age": 14},
    "analysis": {"what": "NOR is close behind PIA.", "why": "Old tyres.", "next": "A stop could pay off."},
}


@pytest.mark.parametrize(
    ("text", "accepted", "reason_part"),
    [
        ("NOR is 1.8 s behind PIA", True, None),
        ("a 62% chance", True, None),
        ("PIA's tyres are 14 laps old", True, None),
        ("about 3 seconds", False, "3"),
        ("HAM could join the fight", False, "HAM"),
    ],
)
def test_check_results_table(text, accepted, reason_part):
    result = check_grounding(text, EVENT)
    assert isinstance(result, Grounding)
    assert result.accepted is accepted
    if accepted:
        assert result.reason is None
    else:
        assert reason_part in result.reason


def test_event_lap_grounds_the_text():
    """Scenario: Event lap grounds the text."""
    event = {**EVENT, "lap": 48, "drivers": ["ZHO"]}
    assert check_grounding("On lap 48 ZHO's tyres are fading", event).accepted
    assert not check_grounding("On lap 49 ZHO's tyres are fading", event).accepted


def test_template_text_numbers_ground_the_text():
    lap_19 = {**EVENT, "lap": 19}
    event = {**lap_19, "analysis": {**EVENT["analysis"], "what": "NOR is close behind PIA on lap 20."}}
    assert check_grounding("On lap 20 NOR is close", event).accepted
    assert not check_grounding("On lap 20 NOR is close", lap_19).accepted


def test_rounding_respects_shown_precision():
    assert check_grounding("a 1.84 s gap", EVENT).accepted
    assert check_grounding("a 2 s gap", EVENT).accepted  # 1.84 rounds to 2
    assert not check_grounding("a 1.9 s gap", EVENT).accepted
    assert not check_grounding("a 1.85 s gap", EVENT).accepted


@pytest.mark.parametrize(
    ("evidence", "text"),
    [({"gap_s": 1.15}, "a 1.2 s gap"), ({"gap_s": 1.25}, "a 1.3 s gap"), ({"p": 0.125}, "a 13% chance")],
)
def test_half_way_values_round_up(evidence, text):
    """Round-half-up is accepted too (Python's round() would round half to even)."""
    event = {**EVENT, "evidence": evidence}
    assert check_grounding(text, event).accepted


def test_percentage_and_fraction_both_ways():
    event = {**EVENT, "analysis": {**EVENT["analysis"], "next": "Pitting wins in 62% of simulations."}}
    assert check_grounding("a 0.62 chance", event).accepted
    assert check_grounding("62 %", EVENT).accepted
    assert not check_grounding("63%", EVENT).accepted
    assert not check_grounding("62 laps", EVENT).accepted  # a bare 62 is not the 0.62 fraction


def test_percentage_matches_only_fractions():
    """A percentage matches a fraction (0..1), never a lap, gap, or tyre age times 100."""
    assert not check_grounding("a 2000% chance", EVENT).accepted  # lap 20
    assert not check_grounding("a 184% chance", EVENT).accepted  # gap_s 1.84
    assert not check_grounding("a 1400% chance", EVENT).accepted  # tyre_age 14
    assert check_grounding("a 100% chance", {**EVENT, "evidence": {"p": 1.0}}).accepted
    assert check_grounding("a 0% chance", {**EVENT, "evidence": {"p": 0.0}}).accepted


def test_nested_evidence_and_driver_codes_in_evidence():
    event = {**EVENT, "drivers": ["NOR"], "evidence": {"ahead": "PIA", "strategy": {"pit_lap": 21}}}
    assert check_grounding("NOR may stop on lap 21 to pass PIA", event).accepted


def test_driver_codes_next_to_chinese_text():
    assert check_grounding("NOR落後PIA 1.8秒", EVENT).accepted
    assert not check_grounding("HAM可能加入戰局", EVENT).accepted


def test_empty_text_is_rejected():
    result = check_grounding("   ", EVENT)
    assert not result.accepted and result.reason == "empty text"
