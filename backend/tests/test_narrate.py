"""Narrate command and commentary cache (llm-commentary 1.4)."""

from __future__ import annotations

import sqlite3

import pytest
from synthetic import write_synthetic_race

from augur import analyze, catalog, narrate, train
from augur.events.outcomes import OUTCOME_FIELDS
from augur.narration import base
from augur.narration.gemini import API_KEY_ENV

RACE = "2098-03-synthetic-grand-prix"


@pytest.fixture(scope="module")
def analyzed(tmp_path_factory):
    d = tmp_path_factory.mktemp("narrate") / "data"
    for rnd, seed in ((1, 1), (2, 2), (3, 3)):
        write_synthetic_race(d, 2098, rnd, seed)
    train.train("baseline", [(2098, 1), (2098, 2)], [(2098, 3)], d)
    assert analyze.main(["--race", RACE, "--model", "baseline", "--data-dir", str(d)]) == 0
    return d


@pytest.fixture
def data(analyzed, tmp_path):
    """A fresh copy of the analyzed data dir per test, so caches never leak between tests."""
    import shutil

    d = tmp_path / "data"
    shutil.copytree(analyzed, d)
    return d


class FakeNarrator:
    name = "gemini"

    def __init__(self, reply=None, model="gemini-test", lang="en") -> None:
        self.llm_model = model
        self.lang = lang
        self.reply = reply or (lambda event: event["analysis"]["what"])
        self.seen: list[dict] = []
        self.last_error = None

    def narrate(self, event):
        self.seen.append(event)
        return self.reply(event)


@pytest.fixture
def fake(monkeypatch):
    narrator = FakeNarrator()
    monkeypatch.delenv("AUGUR_NARRATOR", raising=False)
    monkeypatch.setenv(API_KEY_ENV, "test-key")
    monkeypatch.setitem(base._REGISTRY, "gemini", lambda: narrator)
    return narrator


def run(data, *extra):
    return narrate.main(["--race", RACE, "--model", "baseline", "--data-dir", str(data), *extra])


def n_events(data):
    with sqlite3.connect(catalog.db_path(data)) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM events WHERE race_id = ? AND model = 'baseline'", (RACE,)
        ).fetchone()[0]


def test_second_run_uses_the_cache(data, fake, capsys):
    """Scenario: Second run uses the cache."""
    n = n_events(data)
    assert n > 0
    assert run(data) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == f"narrated {RACE}: {n} ok, 0 rejected, 0 failed, 0 cached"
    assert len(fake.seen) == n
    assert run(data) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == f"narrated {RACE}: 0 ok, 0 rejected, 0 failed, {n} cached"
    assert len(fake.seen) == n  # no LLM call on the second run


def test_cache_key_includes_llm_model_and_lang(data, fake, capsys):
    n = n_events(data)
    assert run(data) == 0
    fake.llm_model = "gemini-other"
    assert run(data) == 0
    assert f"{n} ok" in capsys.readouterr().out.strip().splitlines()[-1]
    fake.lang = "zh-TW"
    assert run(data) == 0
    assert f"{n} ok" in capsys.readouterr().out.strip().splitlines()[-1]


def test_no_key(data, monkeypatch, capsys):
    """Scenario: No key."""
    monkeypatch.delenv("AUGUR_NARRATOR", raising=False)
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    assert run(data) == 0
    assert capsys.readouterr().out.strip() == "GEMINI_API_KEY not set; nothing generated"


def test_narrator_never_sees_outcomes(data, fake):
    assert run(data) == 0
    assert fake.seen
    for event in fake.seen:
        assert not set(OUTCOME_FIELDS) & set(event)


def test_rejected_and_failed_are_counted_and_not_cached(data, fake, capsys):
    n = n_events(data)
    calls = {"n": 0}

    def reply(event):
        calls["n"] += 1
        return None if calls["n"] == 1 else "ZZZ takes the lead"

    fake.reply = reply
    assert run(data) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[-1] == f"narrated {RACE}: 0 ok, {n - 1} rejected, 1 failed, 0 cached"
    assert any(line.startswith("rejected ") and line.endswith(": driver ZZZ not in event") for line in out)
    fake.reply = lambda event: event["analysis"]["what"]
    assert run(data) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == f"narrated {RACE}: {n} ok, 0 rejected, 0 failed, 0 cached"


def test_stored_row(data, fake):
    assert run(data) == 0
    with sqlite3.connect(catalog.db_path(data)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM commentary LIMIT 1").fetchone()
    assert row["model"] == "baseline" and row["narrator"] == "gemini"
    assert row["llm_model"] == "gemini-test" and row["lang"] == "en"
    assert row["prompt_version"] == narrate.PROMPT_VERSION
    assert row["event_id"].startswith(RACE + ":") and row["text"] and row["created_at"]


def test_not_analyzed_and_unknown_race(data, fake, capsys):
    assert narrate.main(["--race", RACE, "--model", "lightgbm", "--data-dir", str(data)]) == 1
    assert capsys.readouterr().out.strip() == f"race {RACE} is not analyzed for model lightgbm, run augur.analyze first"
    assert narrate.main(["--race", "nope", "--model", "baseline", "--data-dir", str(data)]) == 1
    assert capsys.readouterr().out.strip() == "race not found: nope"


def test_lab_server_selected_by_environment(data, monkeypatch, capsys):
    """Scenario: Lab server selected by environment."""
    lab = FakeNarrator(model="glm")
    lab.name = "openai_compat"
    monkeypatch.setenv("AUGUR_NARRATOR", "openai_compat")
    monkeypatch.setenv("AUGUR_LLM_MODEL", "glm")
    monkeypatch.setitem(base._REGISTRY, "openai_compat", lambda: lab)
    assert run(data) == 0
    assert lab.seen
    with sqlite3.connect(catalog.db_path(data)) as conn:
        rows = set(conn.execute("SELECT narrator, llm_model FROM commentary").fetchall())
    assert rows == {("openai_compat", "glm")}


def test_no_server(data, monkeypatch, capsys):
    """Scenario: No server."""
    monkeypatch.setenv("AUGUR_NARRATOR", "openai_compat")
    monkeypatch.delenv("AUGUR_LLM_BASE_URL", raising=False)
    assert run(data) == 0
    assert capsys.readouterr().out.strip() == "AUGUR_LLM_BASE_URL not set; nothing generated"


def test_flag_overrides_environment(data, fake, monkeypatch):
    monkeypatch.setenv("AUGUR_NARRATOR", "openai_compat")
    monkeypatch.delenv("AUGUR_LLM_BASE_URL", raising=False)
    assert run(data, "--narrator", "gemini") == 0
    assert fake.seen


def test_unknown_narrator_in_environment(data, monkeypatch, capsys):
    monkeypatch.setenv("AUGUR_NARRATOR", "nope")
    assert run(data) == 1
    assert capsys.readouterr().out.strip() == "AUGUR_NARRATOR must be one of gemini, none, openai_compat, got 'nope'"


def test_invalid_server_url_is_an_error(data, monkeypatch, capsys):
    monkeypatch.setenv("AUGUR_NARRATOR", "openai_compat")
    monkeypatch.setenv("AUGUR_LLM_BASE_URL", "file:///etc/passwd")
    assert run(data) == 1
    assert "AUGUR_LLM_BASE_URL must be an http:// or https:// URL" in capsys.readouterr().out


def test_unknown_narrator_is_a_usage_error(data):
    with pytest.raises(SystemExit) as exc:
        run(data, "--narrator", "nope")
    assert exc.value.code == 2
