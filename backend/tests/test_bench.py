import json
import shutil

import pytest
from synthetic import write_synthetic_race

import augur
from augur import bench, train

# Two synthetic stand-ins for the benchmark races; the model trains on rounds 1-3.
STAND_INS = ("2098-04-synthetic-grand-prix", "2098-05-synthetic-grand-prix")
RESULT_KEYS = {
    "model", "author", "races", "position_skill_pct", "brier_model", "brier_baseline",
    "log_loss_model", "log_loss_baseline", "reliability",
    "lap_improvement_pct", "mae_model_s", "mae_baseline_s", "hit_rate", "per_race",
    "seed", "data_source", "augur_version", "generated_at",
}
PER_RACE_KEYS = {
    "race_id", "position_skill_pct", "brier_model", "brier_baseline",
    "log_loss_model", "log_loss_baseline", "reliability",
    "lap_improvement_pct", "mae_model_s", "mae_baseline_s", "hit_rate",
}


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    d = tmp_path_factory.mktemp("bench") / "data"
    for rnd, seed in ((1, 1), (2, 2), (3, 3), (4, 4), (5, 5)):
        write_synthetic_race(d, 2098, rnd, seed)
    train.train("baseline", [(2098, 1), (2098, 2)], [(2098, 3)], d)
    return d


@pytest.fixture
def data(trained, tmp_path):
    # A private copy per test, so analysis written by one test never leaks into another.
    d = tmp_path / "data"
    shutil.copytree(trained, d)
    return d


def run(data, out, model="baseline", races=STAND_INS):
    argv = ["--model", model, "--data-dir", str(data), "--out-dir", str(out), "--runs", "100"]
    return bench.main(argv, races=races)


def test_bench_writes_every_key_and_prints_the_summary(data, tmp_path, capsys):
    out = tmp_path / "bench"
    assert run(data, out) == 0
    result = json.loads((out / "baseline.json").read_text())
    assert set(result) == RESULT_KEYS
    assert [r["race_id"] for r in result["per_race"]] == list(STAND_INS)
    assert all(set(r) == PER_RACE_KEYS for r in result["per_race"])
    assert (result["seed"], result["data_source"], result["augur_version"]) == (42, "openf1", augur.__version__)
    assert result["author"] and result["races"] == list(STAND_INS)
    # The baseline model predicts no change, so it ties the lap-time baseline exactly.
    assert result["lap_improvement_pct"] == 0.0
    printed = capsys.readouterr().out.strip().splitlines()[-1]
    assert printed == bench.summary_line(result)
    assert printed.startswith("baseline: podium skill ") and "lap times match baseline (0.0%)" in printed


# Example: pooled scores
def test_summary_line_pooled_scores_example():
    result = {
        "model": "lightgbm",
        "position_skill_pct": 40.0,
        "lap_improvement_pct": 18.0,
        "hit_rate": {"hits": 9, "resolved": 14, "overall_pct": 64.3},
    }
    assert bench.summary_line(result) == (
        "lightgbm: podium skill 40.0% vs current order, lap times beat baseline by 18.0%, event hit rate 64% (9/14)"
    )


def test_summary_line_trail_and_na_forms():
    result = {
        "model": "mine",
        "position_skill_pct": None,
        "lap_improvement_pct": -3.5,
        "hit_rate": {"hits": 0, "resolved": 0, "overall_pct": None},
    }
    assert bench.summary_line(result) == (
        "mine: podium skill n/a, lap times trail baseline by 3.5%, event hit rate n/a (0/0)"
    )


# Scenario: Same model twice
def test_same_model_twice_gives_equal_files_except_generated_at(data, tmp_path):
    first, second = tmp_path / "one", tmp_path / "two"
    assert run(data, first) == 0
    assert run(data, second) == 0
    a = json.loads((first / "baseline.json").read_text())
    b = json.loads((second / "baseline.json").read_text())
    a.pop("generated_at"), b.pop("generated_at")
    assert a == b


# --- Benchmark races excluded from training, and other refusals (task 2.4) -----------


# Scenario: Trained on a benchmark race
def test_trained_on_a_benchmark_race_is_refused(data, tmp_path, capsys):
    from augur.models import registry

    path = registry.metrics_path(data, "baseline")
    metrics = json.loads(path.read_text())
    metrics["train_races"].append(STAND_INS[1])
    path.write_text(json.dumps(metrics))
    out = tmp_path / "bench"

    assert run(data, out) == 1
    assert capsys.readouterr().out.strip() == f"benchmark race {STAND_INS[1]} is in the training set"
    assert not (out / "baseline.json").exists()


def test_unknown_model_is_refused(data, tmp_path, capsys):
    out = tmp_path / "bench"
    assert run(data, out, model="nope") == 1
    assert capsys.readouterr().out.strip() == "unknown model nope"
    assert not out.exists()


def test_missing_race_is_refused(data, tmp_path, capsys):
    out = tmp_path / "bench"
    assert run(data, out, races=(STAND_INS[0], "2098-09-missing-grand-prix")) == 1
    assert capsys.readouterr().out.strip() == "missing race 2098-09-missing-grand-prix, run augur.ingest first"
    assert not out.exists()


def test_untrained_model_is_refused_without_writing(data, tmp_path, capsys):
    out = tmp_path / "bench"
    assert run(data, out, model="lightgbm") == 1
    assert "lightgbm" in capsys.readouterr().out
    assert not out.exists()


def test_bench_reanalyzes_events_stored_without_outcomes(data, tmp_path):
    assert run(data, tmp_path / "one") == 0
    from augur import catalog

    from augur.replay import ReplayStore

    conn = catalog.connect(data)
    with conn:
        n_outcome_events = conn.execute(
            "SELECT COUNT(*) FROM events WHERE type IN ('undercut_window', 'degradation_warning')"
        ).fetchone()[0]
        conn.execute("UPDATE events SET outcome = NULL, outcome_lap = NULL, outcome_text = NULL")
    conn.close()
    assert n_outcome_events > 0, "the stand-in races must produce outcome-type events for this test"
    stale = [r for r in STAND_INS if bench.needs_analysis(ReplayStore(data), r, "baseline")]
    assert stale  # at least one race has outcome-type events now missing their outcomes

    assert run(data, tmp_path / "two") == 0
    assert not any(bench.needs_analysis(ReplayStore(data), r, "baseline") for r in STAND_INS)
