"""Runtime settings: precedence, /api/settings, commentary status (polish 1.2)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from synthetic import write_synthetic_race

from augur import analyze, catalog, narrate, settings, train
from augur.api import create_app
from augur.models import registry
from augur.narration import base
from augur.narration.cache import CommentaryKey, store_text
from augur.narration.prompt import PROMPT_VERSION

RACE = "2098-03-synthetic-grand-prix"
ENV = ("AUGUR_MODEL", "AUGUR_COMMENTARY_LANG", "AUGUR_NARRATOR", "AUGUR_LLM_BASE_URL", "AUGUR_LLM_MODEL",
       "AUGUR_LLM_API_KEY", "GEMINI_API_KEY", "GEMINI_MODEL")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ENV:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "data"
    write_synthetic_race(d, 2098, 3, 3)
    return d


@pytest.fixture
def trained(tmp_path_factory):
    """A data dir with a trained baseline model and an analyzed race."""
    d = tmp_path_factory.mktemp("trained") / "data"
    for rnd, seed in ((1, 1), (2, 2), (3, 3)):
        write_synthetic_race(d, 2098, rnd, seed)
    train.train("baseline", [(2098, 1), (2098, 2)], [(2098, 3)], d)
    assert analyze.main(["--race", RACE, "--model", "baseline", "--data-dir", str(d)]) == 0
    return d


def write_settings(data, **values) -> None:
    data.mkdir(parents=True, exist_ok=True)
    settings.settings_path(data).write_text(json.dumps(values))


@pytest.fixture
def mymodel():
    class MyModel:
        name = "mymodel"
        author = "me"

        def fit(self, *a): ...
        def predict(self, *a): ...
        def save(self, *a): ...
        @classmethod
        def load(cls, *a): ...

    registry.register(MyModel)
    yield
    registry.unregister("mymodel")


# -- precedence ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("stored", "env", "served"),
    [("mymodel", "baseline", "mymodel"), (None, "baseline", "baseline"), (None, None, "lightgbm")],
)
def test_model_resolution(data, monkeypatch, mymodel, stored, env, served):
    """Example: model resolution."""
    if stored:
        write_settings(data, model=stored)
    if env:
        monkeypatch.setenv("AUGUR_MODEL", env)
    assert settings.current(data).model == served


def test_defaults_and_env_for_language(data, monkeypatch):
    assert settings.current(data) == settings.Settings("lightgbm", "en", "replay")
    monkeypatch.setenv("AUGUR_COMMENTARY_LANG", "zh-TW")
    assert settings.current(data).commentary_lang == "zh-TW"
    write_settings(data, commentary_lang="en")
    assert settings.current(data).commentary_lang == "en"


def test_broken_settings_file_falls_back(data, monkeypatch):
    data.mkdir(parents=True, exist_ok=True)
    settings.settings_path(data).write_text("{not json")
    monkeypatch.setenv("AUGUR_MODEL", "baseline")
    assert settings.current(data).model == "baseline"


def test_api_serves_the_settings_model_without_restart(trained, monkeypatch):
    monkeypatch.setenv("AUGUR_MODEL", "lightgbm")
    client = TestClient(create_app(trained))
    assert client.get(f"/api/races/{RACE}/events?lap=10").json()["model"] == "lightgbm"
    assert client.put("/api/settings", json={"model": "baseline"}).status_code == 200
    body = client.get(f"/api/races/{RACE}/events?lap=10").json()
    assert body["model"] == "baseline" and body["analyzed"] is True


# -- PUT cases -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "status", "detail"),
    [
        ({"model": "baseline"}, 200, None),
        ({"model": "nope"}, 422, "unknown model nope"),
        ({"commentary_lang": "ja"}, 422, "unsupported language ja"),
        ({"data_source": "live"}, 422, "live data is not available yet"),
        ({"gemini_api_key": "abc"}, 422, "unknown field gemini_api_key"),
        ({"narrator": "gemini"}, 422, "unknown field narrator"),
    ],
)
def test_put_cases(trained, body, status, detail):
    """Example: PUT cases."""
    response = TestClient(create_app(trained)).put("/api/settings", json=body)
    assert response.status_code == status
    if detail:
        assert response.json()["detail"] == detail
    else:
        assert response.json()["model"] == "baseline"
        assert json.loads(settings.settings_path(trained).read_text()) == {"model": "baseline"}


def test_untrained_model_rejected(data):
    response = TestClient(create_app(data)).put("/api/settings", json={"model": "lightgbm"})
    assert response.status_code == 422 and response.json()["detail"] == "model lightgbm is not trained"


def test_put_rejects_wrong_types_and_non_objects(trained):
    client = TestClient(create_app(trained))
    assert client.put("/api/settings", json={"model": 5}).json()["detail"] == "unknown model 5"
    assert client.put("/api/settings", json=["model"]).status_code == 422
    assert client.put("/api/settings", json={"data_source": "tape"}).json()["detail"] == "unknown data source tape"


def test_put_merges_and_a_failed_put_writes_nothing(trained):
    client = TestClient(create_app(trained))
    client.put("/api/settings", json={"commentary_lang": "zh-TW"})
    client.put("/api/settings", json={"model": "baseline"})
    client.put("/api/settings", json={"model": "baseline", "commentary_lang": "ja"})
    stored = json.loads(settings.settings_path(trained).read_text())
    assert stored == {"commentary_lang": "zh-TW", "model": "baseline"}


def test_get_shape(trained):
    body = TestClient(create_app(trained)).get("/api/settings").json()
    assert body["model"] == "lightgbm" and body["commentary_lang"] == "en" and body["data_source"] == "replay"
    models = {m["name"]: m for m in body["models"]}
    assert models["baseline"]["trained"] is True and models["lightgbm"]["trained"] is False
    assert isinstance(models["baseline"]["author"], str)
    assert body["commentary_langs"] == ["en", "zh-TW"]
    assert body["data_sources"] == [{"name": "replay", "available": True}, {"name": "live", "available": False}]


# -- commentary status ---------------------------------------------------------


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"AUGUR_NARRATOR": "openai_compat", "AUGUR_LLM_BASE_URL": "http://lab:11400/v1", "AUGUR_LLM_MODEL": "glm"},
         {"narrator": "openai_compat", "llm_model": "glm", "configured": True, "missing": None}),
        ({"AUGUR_NARRATOR": "openai_compat"},
         {"narrator": "openai_compat", "llm_model": "glm", "configured": False, "missing": "AUGUR_LLM_BASE_URL"}),
        ({"AUGUR_NARRATOR": "gemini", "GEMINI_API_KEY": "k"},
         {"narrator": "gemini", "llm_model": "gemini-flash-latest", "configured": True, "missing": None}),
        ({"AUGUR_NARRATOR": "none"}, {"narrator": "none", "llm_model": None, "configured": False, "missing": None}),
    ],
)
def test_commentary_status(data, monkeypatch, env, expected):
    """Example: commentary status."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert TestClient(create_app(data)).get("/api/settings").json()["commentary"] == expected


def test_secrets_never_exposed(data, monkeypatch):
    """Scenario: Secrets never exposed."""
    secrets = {"GEMINI_API_KEY": "gem-SECRET-123", "AUGUR_LLM_API_KEY": "lab-SECRET-456",
               "AUGUR_LLM_BASE_URL": "http://10.9.8.7:11400/v1"}
    for k, v in secrets.items():
        monkeypatch.setenv(k, v)
    client = TestClient(create_app(data))
    for text in (client.get("/api/settings").text, client.put("/api/settings", json={"data_source": "replay"}).text):
        for value in secrets.values():
            assert value not in text
        assert "SECRET" not in text and "10.9.8.7" not in text


# -- commentary language follows settings ----------------------------------------


def test_commentary_language_follows_settings(trained, monkeypatch):
    """Scenario: Commentary language follows settings."""
    monkeypatch.setenv("AUGUR_COMMENTARY_LANG", "en")
    monkeypatch.setenv("AUGUR_NARRATOR", "openai_compat")
    monkeypatch.setenv("AUGUR_LLM_MODEL", "glm")
    write_settings(trained, model="baseline", commentary_lang="zh-TW")
    client = TestClient(create_app(trained))
    first = client.get(f"/api/races/{RACE}/events?lap=30").json()["events"][0]["id"]

    conn = catalog.connect(trained)
    with conn:
        for lang, text in (("en", "english text"), ("zh-TW", "中文評論")):
            store_text(conn, first, CommentaryKey("baseline", "openai_compat", "glm", lang, PROMPT_VERSION), text)
    conn.close()
    events = client.get(f"/api/races/{RACE}/events?lap=30").json()["events"]
    assert {e["id"]: e["commentary"] for e in events}[first] == "中文評論"

    class Lab:
        name = "openai_compat"
        llm_model = "glm"
        lang = "en"
        last_error = None

        def narrate(self, event):
            return event["analysis"]["what"]

    lab = Lab()
    monkeypatch.setitem(base._REGISTRY, "openai_compat", lambda: lab)
    assert narrate.main(["--race", RACE, "--model", "baseline", "--data-dir", str(trained)]) == 0
    assert lab.lang == "zh-TW"
    conn = catalog.connect(trained)
    new_langs = {r[0] for r in conn.execute(
        "SELECT lang FROM commentary WHERE text NOT IN ('中文評論', 'english text')")}
    conn.close()
    assert new_langs == {"zh-TW"}
