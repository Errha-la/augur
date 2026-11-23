import json
import shutil

import pytest
from synthetic import write_synthetic_race

from augur import bench, train

# Synthetic stand-ins: the model trains on 2098 rounds 1-3; rounds 4-5 are the benchmark
# stand-ins and rounds 6-7 the evaluation stand-ins.
STAND_INS = ("2098-04-synthetic-grand-prix", "2098-05-synthetic-grand-prix")
EVAL = ((2098, 6), (2098, 7))


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    d = tmp_path_factory.mktemp("bench-eval") / "data"
    for rnd in range(1, 8):
        write_synthetic_race(d, 2098, rnd, rnd)
    train.train("baseline", [(2098, 1), (2098, 2)], [(2098, 3)], d)
    return d


@pytest.fixture
def data(trained, tmp_path):
    d = tmp_path / "data"
    shutil.copytree(trained, d)
    return d


def run(data, out, *extra, eval_rounds=EVAL):
    argv = ["--model", "baseline", "--data-dir", str(data), "--out-dir", str(out), "--runs", "100", *extra]
    return bench.main(argv, races=STAND_INS, eval_rounds=eval_rounds)


def test_eval_rounds_are_2024_rounds_12_to_23():
    assert bench.EVAL_ROUNDS == tuple((2024, r) for r in range(12, 24))


# Scenario: Evaluation race missing
def test_evaluation_race_missing(data, tmp_path, capsys):
    out = tmp_path / "bench"
    assert run(data, out, "--eval", eval_rounds=((2098, 6), (2098, 15))) == 1
    assert capsys.readouterr().out.strip() == "missing race 2098-15, run augur.ingest first"
    assert not out.exists()


# Scenario: Benchmark file untouched
def test_benchmark_file_untouched(data, tmp_path, capsys):
    out = tmp_path / "bench"
    assert run(data, out) == 0
    before = (out / "baseline.json").read_bytes()
    assert run(data, out, "--eval") == 0
    assert (out / "baseline.json").read_bytes() == before
    result = json.loads((out / "baseline-eval.json").read_text())
    assert result["races"] == ["2098-06-synthetic-grand-prix", "2098-07-synthetic-grand-prix"]
    assert set(result) == set(json.loads(before))
    assert capsys.readouterr().out.strip().splitlines()[-1] == bench.summary_line(result)


# Scenario: Tuning grid output
def test_tuning_grid_output(data, capsys):
    import re

    from augur import config, tune_sim

    saved = (config.PACE_OFFSET_SD_S, config.MODEL_DELTA_DECAY)
    argv = ["--model", "baseline", "--data-dir", str(data), "--runs", "100"]
    assert tune_sim.main(argv, eval_rounds=EVAL) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 15
    pattern = re.compile(r"offset_sd=\d\.\d\d decay=\d\.\d brier=\d\.\d+ log_loss=\d\.\d+")
    assert all(pattern.fullmatch(line) for line in lines)
    assert lines[0].startswith("offset_sd=0.05 decay=0.3 ") and lines[-1].startswith("offset_sd=0.30 decay=0.7 ")
    assert (config.PACE_OFFSET_SD_S, config.MODEL_DELTA_DECAY) == saved  # restored


def test_tuning_missing_race_is_refused(data, capsys):
    from augur import tune_sim

    argv = ["--model", "baseline", "--data-dir", str(data), "--runs", "100"]
    assert tune_sim.main(argv, eval_rounds=((2098, 15),)) == 1
    assert capsys.readouterr().out.strip() == "missing race 2098-15, run augur.ingest first"


def test_eval_unknown_model_is_refused(data, tmp_path, capsys):
    argv = ["--model", "nope", "--eval", "--data-dir", str(data), "--out-dir", str(tmp_path / "b")]
    assert bench.main(argv, eval_rounds=((2098, 99),)) == 1
    assert capsys.readouterr().out.strip() == "unknown model nope"
