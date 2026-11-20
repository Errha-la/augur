import math

import pytest
from synthetic import write_synthetic_race

from augur import analyze, train
from augur.scoring import (
    RaceInputs,
    checkpoints,
    hit_rate,
    lap_scores,
    podium_pairs,
    podium_skill,
    race_inputs,
    scores,
)


# specs/model-benchmark "Checkpoint laps"
@pytest.mark.parametrize("total_laps, expected", [(57, [14, 28, 42]), (58, [14, 29, 43])])
def test_checkpoint_laps(total_laps, expected):
    assert checkpoints(total_laps) == expected


# Example: one checkpoint, four drivers
def test_one_checkpoint_four_drivers():
    pairs = podium_pairs(
        {20: {"A": 1, "B": 2, "C": 3, "D": 4}},
        {20: {"A": 0.9, "B": 0.8, "C": 0.5, "D": 0.4}},
        ["A", "B", "D"],
    )
    assert podium_skill(pairs) == {"brier_model": 0.165, "brier_baseline": 0.5, "position_skill_pct": 67.0}


# Scenario: Podium never changed
def test_podium_never_changed_gives_null_skill():
    order = {"A": 1, "B": 2, "C": 3, "D": 4}
    pairs = podium_pairs(
        {14: order, 28: order, 42: order},
        {14: {"A": 0.9, "B": 0.8, "C": 0.7, "D": 0.1}},
        ["A", "B", "C"],
    )
    result = podium_skill(pairs)
    assert result["brier_baseline"] == 0.0
    assert result["position_skill_pct"] is None
    assert result["brier_model"] > 0


def test_missing_forecast_counts_as_zero_and_skill_can_be_negative():
    pairs = podium_pairs({10: {"A": 1, "B": 4}}, {10: {"A": None}}, ["B"])
    assert pairs == [(0.0, 1.0, 0), (0.0, 0.0, 1)]
    # model (0² + 1²) / 2 = 0.5, baseline (1² + 1²) / 2 = 1.0 → 50.0
    assert podium_skill(pairs)["position_skill_pct"] == 50.0
    # model (0.8² + 1²) / 2 = 0.82, baseline (0² + 1²) / 2 = 0.5 → -64.0
    assert podium_skill([(0.2, 1.0, 1), (0.0, 0.0, 1)]) == {
        "brier_model": 0.82,
        "brier_baseline": 0.5,
        "position_skill_pct": -64.0,
    }


def test_no_pairs():
    assert podium_skill([])["position_skill_pct"] is None


def test_a_tie_is_zero_not_negative_zero():
    tie = podium_skill([(0.3, 1.0, 1), (0.7, 0.0, 1)])  # model 0.49+0.09, baseline 0+1 → not a tie
    assert tie["position_skill_pct"] != 0.0
    same = podium_skill([(1.0, 1.0, 0), (0.0, 0.0, 0)])  # identical errors → exactly 0
    assert str(same["position_skill_pct"]) == "0.0"
    assert str(lap_scores([1.0000001], [1.0])["lap_improvement_pct"]) == "0.0"


# --- Shared scoring (task 2.2) -------------------------------------------------------


def calls(type_, outcomes):
    return [{"type": type_, "outcome": o} for o in outcomes]


# Example: pooled scores — brier 0.060 / 0.100, MAE 0.820 / 1.000, 9 hits, 5 misses, 2 voids
def test_pooled_scores_example():
    m = 1 - math.sqrt(0.6)  # (m - 1)² = 0.6: one baseline-wrong pair carries the model's whole error
    race_a = RaceInputs(
        race_id="a",
        pairs=[(m, 0.0, 1)] + [(0.0, 0.0, 0)] * 4,
        err_model=[0.80, 0.84],
        err_baseline=[1.0, 1.0],
        events=calls("undercut_window", ["hit"] * 5 + ["miss"] * 2 + ["void"]),
    )
    race_b = RaceInputs(
        race_id="b",
        pairs=[(0.0, 0.0, 0)] * 5,
        err_model=[0.82],
        err_baseline=[1.0],
        events=calls("degradation_warning", ["hit"] * 4 + ["miss"] * 3 + ["void"]) + calls("pace_drop", [None]),
    )
    pooled = scores([race_a, race_b])
    assert (pooled["brier_model"], pooled["brier_baseline"], pooled["position_skill_pct"]) == (0.06, 0.1, 40.0)
    assert (pooled["mae_model_s"], pooled["mae_baseline_s"], pooled["lap_improvement_pct"]) == (0.82, 1.0, 18.0)
    hr = pooled["hit_rate"]
    assert (hr["hits"], hr["resolved"], hr["overall_pct"]) == (9, 14, 64.3)
    assert hr["undercut"] == {"hits": 5, "resolved": 7}
    assert hr["degradation"] == {"hits": 4, "resolved": 7}
    # Per race: race b has no podium change at all, so its skill is undefined.
    assert scores([race_b])["position_skill_pct"] is None


def test_lap_scores_and_hit_rate_edge_cases():
    assert lap_scores([], [])["lap_improvement_pct"] is None
    assert lap_scores([1.0], [1.0])["lap_improvement_pct"] == 0.0
    assert lap_scores([1.2], [1.0])["lap_improvement_pct"] == -20.0
    assert hit_rate(calls("undercut_window", ["void"]))["overall_pct"] is None


def test_race_inputs_from_an_analyzed_race(tmp_path):
    d = tmp_path / "data"
    for rnd, seed in ((1, 1), (2, 2), (3, 3)):
        write_synthetic_race(d, 2098, rnd, seed)
    train.train("baseline", [(2098, 1), (2098, 2)], [(2098, 3)], d)
    race = "2098-03-synthetic-grand-prix"
    assert analyze.main(["--race", race, "--model", "baseline", "--runs", "100", "--data-dir", str(d)]) == 0

    inputs = race_inputs(d, race, "baseline")
    assert len(inputs.pairs) == 3 * 6  # 3 checkpoints of a 30-lap race x 6 drivers
    assert inputs.err_model == inputs.err_baseline  # the baseline model predicts 0
    assert len(inputs.err_model) > 0
    assert all(e["outcome"] in ("hit", "miss", "void", None) for e in inputs.events)
    result = scores([inputs])
    assert result["lap_improvement_pct"] == 0.0
    assert result["brier_model"] is not None
