import json

import pandas as pd
import pytest
from synthetic import write_synthetic_race

from augur import train
from augur.features import FEATURE_COLUMNS
from augur.models import registry
from augur.models.base import JoblibModel

METRIC_KEYS = {
    "model", "author", "train_races", "test_races", "n_train", "n_test",
    "mae_model_s", "mae_baseline_s", "trained_at",
}


class MyModel(JoblibModel):
    name = "mymodel"
    author = "tester"
    seen_columns: list[str] = []

    def fit(self, features, target):
        MyModel.seen_columns = list(features.columns)
        self.mean_ = float(target.mean())

    def predict(self, features):
        return pd.Series(self.mean_, index=features.index)


@pytest.fixture
def mymodel():
    registry.register(MyModel)
    yield MyModel
    registry.unregister("mymodel")


@pytest.fixture
def three_races(tmp_path):
    data = tmp_path / "data"
    for rnd, seed in ((1, 1), (2, 2), (3, 3)):
        write_synthetic_race(data, 2098, rnd, seed)
    return data


@pytest.mark.parametrize("name", ["mymodel", "lightgbm"])
def test_train_writes_model_and_metrics(three_races, mymodel, name, capsys):
    code = train.main(["--model", name, "--train", "2098:1-2", "--test", "2098:3",
                       "--data-dir", str(three_races)])
    assert code == 0
    metrics_file = three_races / "models" / f"{name}_metrics.json"
    assert (three_races / "models" / f"{name}.joblib").is_file()
    metrics = json.loads(metrics_file.read_text())
    assert set(metrics) == METRIC_KEYS
    assert metrics["model"] == name
    assert metrics["author"] == ("tester" if name == "mymodel" else "AUGUR")
    assert metrics["train_races"] == ["2098-01-synthetic-grand-prix", "2098-02-synthetic-grand-prix"]
    assert metrics["test_races"] == ["2098-03-synthetic-grand-prix"]
    assert metrics["n_train"] > 0 and metrics["n_test"] > 0
    out = capsys.readouterr().out
    assert f"mae_model_s={metrics['mae_model_s']:.4f}" in out
    assert f"mae_baseline_s={metrics['mae_baseline_s']:.4f}" in out


def test_model_receives_only_feature_columns(three_races, mymodel):
    train.main(["--model", "mymodel", "--train", "2098:1-2", "--test", "2098:3", "--data-dir", str(three_races)])
    assert MyModel.seen_columns == list(FEATURE_COLUMNS)
    assert "driver" not in MyModel.seen_columns


def test_lightgbm_is_deterministic(three_races):
    args = ["--model", "lightgbm", "--train", "2098:1-2", "--test", "2098:3", "--data-dir", str(three_races)]
    train.main(args)
    first = json.loads((three_races / "models" / "lightgbm_metrics.json").read_text())["mae_model_s"]
    train.main(args)
    second = json.loads((three_races / "models" / "lightgbm_metrics.json").read_text())["mae_model_s"]
    assert first == second


def test_parse_race_lists():
    assert train.parse_races("2024:2-11") == [(2024, r) for r in range(2, 12)]
    assert train.parse_races("2024:1,24") == [(2024, 1), (2024, 24)]
    for bad in ("2024", "2024:", "2024:5-2", "x:1", "2024:0", "2024:1-100"):
        with pytest.raises(ValueError):
            train.parse_races(bad)


def test_defaults_are_2024_rounds():
    args = train._parser().parse_args([])
    assert args.train == [(2024, r) for r in range(2, 12)]
    assert args.test == [(2024, 1), (2024, 24)]
    assert args.model == "lightgbm"


def test_missing_race_message(three_races, capsys):
    code = train.main(["--train", "2098:1-2", "--test", "2098:9", "--data-dir", str(three_races)])
    assert code == 1
    assert capsys.readouterr().out.strip() == "missing race 2098-09, run augur.ingest first"


def test_unknown_model_message(three_races, capsys):
    code = train.main(["--model", "nope", "--data-dir", str(three_races)])
    assert code == 1
    assert capsys.readouterr().out.strip() == "unknown model nope"


def test_overlap_message(three_races, capsys):
    code = train.main(["--train", "2098:1-2", "--test", "2098:2,3", "--data-dir", str(three_races)])
    assert code == 1
    assert capsys.readouterr().out.strip() == "train and test races overlap: 2098-02-synthetic-grand-prix"
    assert not (three_races / "models").exists()
