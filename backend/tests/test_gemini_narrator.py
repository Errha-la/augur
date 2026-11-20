"""GeminiNarrator with a fake google-genai client (llm-commentary 1.2)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from augur.narration import build_prompt, get_narrator, narrator_names
from augur.narration.gemini import (
    API_KEY_ENV,
    DEFAULT_MODEL,
    MAX_OUTPUT_TOKENS,
    MODEL_ENV,
    RETRY_WAITS_S,
    TEMPERATURE,
    GeminiNarrator,
    MissingApiKeyError,
)

EVENT = {
    "id": "r:20:undercut_window:NOR-PIA",
    "lap": 20,
    "type": "undercut_window",
    "drivers": ["NOR", "PIA"],
    "analysis": {"what": "NOR is 1.8 s behind PIA.", "why": "Old tyres.", "next": "A stop could pay off."},
    "evidence": {"gap_s": 1.84},
    "outcome": "hit",
}


class FakeApiError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"{code}")
        self.code = code


class FakeModels:
    def __init__(self, results: list) -> None:
        self.results = list(results)
        self.calls: list[dict] = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(text=result)


def _narrator(results, lang="en", model="gemini-test"):
    models = FakeModels(results)
    waits: list[float] = []
    narrator = GeminiNarrator(
        client=SimpleNamespace(models=models), model=model, lang=lang, sleep=waits.append
    )
    return narrator, models, waits


def test_success_sends_prompt_and_settings():
    narrator, models, waits = _narrator(["  NOR is closing on PIA.  "])
    assert narrator.narrate(EVENT) == "NOR is closing on PIA."
    (call,) = models.calls
    assert call["model"] == "gemini-test"
    assert call["contents"] == build_prompt(EVENT, "en")
    assert call["config"] == {"temperature": TEMPERATURE, "max_output_tokens": MAX_OUTPUT_TOKENS}
    assert (TEMPERATURE, MAX_OUTPUT_TOKENS) == (0.4, 200)
    assert waits == []


def test_one_retry_then_success():
    narrator, models, waits = _narrator([FakeApiError(503), "NOR could undercut PIA."])
    assert narrator.narrate(EVENT) == "NOR could undercut PIA."
    assert len(models.calls) == 2
    assert waits == [2.0]


def test_three_failures_return_none():
    narrator, models, waits = _narrator([FakeApiError(429), FakeApiError(500), FakeApiError(503)])
    assert narrator.narrate(EVENT) is None
    assert len(models.calls) == 3
    assert waits == list(RETRY_WAITS_S) == [2.0, 4.0]


def test_non_retryable_error_returns_none_without_retry():
    narrator, models, waits = _narrator([FakeApiError(400)])
    assert narrator.narrate(EVENT) is None
    assert len(models.calls) == 1 and waits == []


def test_empty_response_returns_none():
    narrator, _, _ = _narrator([None])
    assert narrator.narrate(EVENT) is None
    narrator, _, _ = _narrator(["   "])
    assert narrator.narrate(EVENT) is None


def test_lang_is_used_in_prompt():
    narrator, models, _ = _narrator(["NOR 正在追近 PIA。"], lang="zh-TW")
    narrator.narrate(EVENT)
    assert models.calls[0]["contents"] == build_prompt(EVENT, "zh-TW")


def test_model_and_lang_from_env(monkeypatch):
    monkeypatch.delenv(MODEL_ENV, raising=False)
    monkeypatch.delenv("AUGUR_COMMENTARY_LANG", raising=False)
    narrator = GeminiNarrator(client=SimpleNamespace(models=FakeModels([])))
    assert narrator.llm_model == DEFAULT_MODEL == "gemini-flash-latest"
    assert narrator.lang == "en"
    monkeypatch.setenv(MODEL_ENV, "gemini-4-hydrogen")
    assert GeminiNarrator(client=SimpleNamespace(models=FakeModels([]))).llm_model == "gemini-4-hydrogen"


@pytest.mark.parametrize("bad", ["../models", "gemini flash", "a" * 100])
def test_invalid_model_name_fails_loudly(monkeypatch, bad):
    monkeypatch.setenv(MODEL_ENV, bad)
    with pytest.raises(ValueError, match=MODEL_ENV):
        GeminiNarrator(client=SimpleNamespace(models=FakeModels([])))


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(MissingApiKeyError, match="GEMINI_API_KEY not set"):
        GeminiNarrator()


def test_registered_as_gemini(monkeypatch):
    assert "gemini" in narrator_names()
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(MissingApiKeyError):
        get_narrator("gemini")
