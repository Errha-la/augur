"""OpenAICompatNarrator with a fake HTTP opener (llm-commentary 1.5)."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from augur.narration import build_prompt, get_narrator, narrator_names
from augur.narration.base import MissingSettingError
from augur.narration.openai_compat import (
    API_KEY_ENV,
    BASE_URL_ENV,
    DEFAULT_MODEL,
    MODEL_ENV,
    TIMEOUT_S,
    OpenAICompatNarrator,
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


def _reply(content) -> bytes:
    return json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://lab/v1/chat/completions", code, "err", {}, io.BytesIO(b"{}"))


class FakeOpener:
    def __init__(self, results: list) -> None:
        self.results = list(results)
        self.requests: list = []
        self.timeouts: list = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        self.timeouts.append(timeout)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return io.BytesIO(result)


def _narrator(results, **kwargs):
    opener = FakeOpener(results)
    waits: list[float] = []
    kwargs.setdefault("base_url", "http://lab:11400/v1/")
    kwargs.setdefault("model", "glm")
    kwargs.setdefault("lang", "en")
    narrator = OpenAICompatNarrator(opener=opener, sleep=waits.append, **kwargs)
    return narrator, opener, waits


def test_request_body_and_headers(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    narrator, opener, waits = _narrator([_reply("  NOR is closing on PIA.  ")])
    assert narrator.narrate(EVENT) == "NOR is closing on PIA."
    (req,) = opener.requests
    assert req.full_url == "http://lab:11400/v1/chat/completions"
    assert req.get_method() == "POST"
    assert req.get_header("Content-type") == "application/json"
    assert req.get_header("Authorization") is None
    body = json.loads(req.data)
    assert body == {
        "model": "glm",
        "messages": [{"role": "user", "content": build_prompt(EVENT, "en")}],
        "temperature": 0.4,
        "max_tokens": 200,
    }
    assert opener.timeouts == [TIMEOUT_S] and waits == []


def test_bearer_header_only_when_key_set():
    narrator, opener, _ = _narrator([_reply("ok")], api_key="secret")
    narrator.narrate(EVENT)
    assert opener.requests[0].get_header("Authorization") == "Bearer secret"


def test_thinking_block_removed():
    """Scenario: Thinking block removed."""
    narrator, _, _ = _narrator([_reply("<think>check the gap</think>NOR is 1.8 s behind PIA.")])
    assert narrator.narrate(EVENT) == "NOR is 1.8 s behind PIA."


def test_only_thinking_or_empty_returns_none():
    for content in ("<think>hmm</think>", "", None):
        narrator, _, _ = _narrator([_reply(content)])
        assert narrator.narrate(EVENT) is None


def test_one_retry_then_success():
    narrator, opener, waits = _narrator([_http_error(503), _reply("NOR could undercut PIA.")])
    assert narrator.narrate(EVENT) == "NOR could undercut PIA."
    assert len(opener.requests) == 2 and waits == [2.0]


def test_three_failures_return_none():
    narrator, opener, waits = _narrator([_http_error(429), _http_error(500), _http_error(502)])
    assert narrator.narrate(EVENT) is None
    assert len(opener.requests) == 3 and waits == [2.0, 4.0]
    assert narrator.last_error.code == 502


def test_connection_error_and_bad_json_fail_without_retry():
    narrator, opener, waits = _narrator([urllib.error.URLError("refused")])
    assert narrator.narrate(EVENT) is None
    assert len(opener.requests) == 1 and waits == []
    narrator, _, _ = _narrator([b"not json"])
    assert narrator.narrate(EVENT) is None
    narrator, _, _ = _narrator([json.dumps({"choices": []}).encode()])
    assert narrator.narrate(EVENT) is None


@pytest.mark.parametrize("bad", ["file:///etc/passwd", "lab:11400/v1", "ftp://lab/v1", "http://"])
def test_invalid_base_url(bad):
    """Scenario: Invalid base URL."""
    with pytest.raises(ValueError, match=BASE_URL_ENV):
        OpenAICompatNarrator(base_url=bad, model="glm", lang="en")


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv(BASE_URL_ENV, "http://lab:11400/v1")
    monkeypatch.delenv(MODEL_ENV, raising=False)
    monkeypatch.setenv(API_KEY_ENV, "k")
    monkeypatch.setenv("AUGUR_COMMENTARY_LANG", "zh-TW")
    narrator = OpenAICompatNarrator(opener=FakeOpener([]))
    assert narrator.llm_model == DEFAULT_MODEL == "glm"
    assert narrator.lang == "zh-TW"
    monkeypatch.setenv(MODEL_ENV, "Qwen/Qwen3-32B")
    assert OpenAICompatNarrator(opener=FakeOpener([])).llm_model == "Qwen/Qwen3-32B"
    monkeypatch.setenv(MODEL_ENV, "bad model name")
    with pytest.raises(ValueError, match=MODEL_ENV):
        OpenAICompatNarrator(opener=FakeOpener([]))


def test_missing_base_url(monkeypatch):
    monkeypatch.delenv(BASE_URL_ENV, raising=False)
    with pytest.raises(MissingSettingError) as exc:
        get_narrator("openai_compat")
    assert exc.value.setting == BASE_URL_ENV
    assert str(exc.value) == "AUGUR_LLM_BASE_URL not set"


def test_registered():
    assert {"none", "gemini", "openai_compat"} <= set(narrator_names())
