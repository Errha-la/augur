import pandas as pd
import pytest

from augur.models import registry
from augur.models.base import JoblibModel, LapTimeModel
from augur.models.baseline import BaselineModel


class MyModel(JoblibModel):
    name = "mymodel"
    author = "tester"

    def fit(self, features, target):
        self.mean_ = float(target.mean())

    def predict(self, features):
        return pd.Series(self.mean_, index=features.index)


@pytest.fixture
def mymodel():
    registry.register(MyModel)
    yield MyModel
    registry.unregister("mymodel")


def test_custom_model_resolves_by_name(mymodel):
    assert registry.get_model_class("mymodel") is MyModel
    assert isinstance(registry.create_model("mymodel"), LapTimeModel)
    assert "mymodel" in registry.model_names()


def test_unknown_model_error_message():
    with pytest.raises(registry.UnknownModelError) as exc:
        registry.get_model_class("nope")
    assert str(exc.value) == "unknown model nope"


def test_baseline_predicts_zero_delta():
    model = registry.create_model("baseline")
    features = pd.DataFrame({"tyre_life": [1.0, 2.0]})
    model.fit(features, pd.Series([0.3, -0.1]))
    assert model.predict(features).tolist() == [0.0, 0.0]
    assert model.author == "AUGUR"


@pytest.mark.parametrize("bad", ["../evil", "Upper", "", "a" * 41, "has-dash"])
def test_register_rejects_unsafe_names(bad):
    cls = type("Bad", (BaselineModel,), {"name": bad})
    with pytest.raises(ValueError):
        registry.register(cls)


def test_register_rejects_missing_methods():
    cls = type("NoPredict", (), {"name": "nopredict", "author": "x", "fit": lambda s, f, t: None})
    with pytest.raises(ValueError, match="predict"):
        registry.register(cls)


def test_load_refuses_other_class(tmp_path, mymodel):
    path = tmp_path / "x.joblib"
    BaselineModel().save(path)
    with pytest.raises(TypeError):
        MyModel.load(path)


def test_load_trained_missing_file(tmp_path):
    with pytest.raises(registry.ModelNotTrainedError, match="model baseline is not trained"):
        registry.load_trained(tmp_path, "baseline")


def test_model_path_rejects_unregistered_names(tmp_path):
    with pytest.raises(registry.UnknownModelError):
        registry.model_path(tmp_path, "../../etc/passwd")
