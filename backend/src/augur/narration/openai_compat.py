"""Narrator for OpenAI-compatible chat servers (vLLM, SGLang, llama.cpp, routers).

Built for the lab's self-hosted model server: one POST to
``<AUGUR_LLM_BASE_URL>/chat/completions`` with the standard library, so no
SDK is needed.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from augur.narration.base import MissingSettingError, call_with_retries, register
from augur.narration.prompt import build_prompt, commentary_lang

BASE_URL_ENV = "AUGUR_LLM_BASE_URL"
MODEL_ENV = "AUGUR_LLM_MODEL"
API_KEY_ENV = "AUGUR_LLM_API_KEY"
DEFAULT_MODEL = "glm"
TEMPERATURE = 0.4
MAX_TOKENS = 200
# Estimate: the lab router loads an unloaded model on the first request; measure the
# cold-load time there and raise this only with evidence.
TIMEOUT_S = 120.0

# Router aliases (glm), Hugging Face ids (Qwen/Qwen3-32B), Ollama tags (qwen3:8b).
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\-]{0,127}$")
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

Opener = Callable[..., Any]


def configured_model() -> str:
    """$AUGUR_LLM_MODEL (unset or empty: glm), validated."""
    model = os.environ.get(MODEL_ENV) or DEFAULT_MODEL
    return _check_model(model)


def _check_model(model: str) -> str:
    if not MODEL_RE.fullmatch(model):
        raise ValueError(f"{MODEL_ENV} must be a model id like {DEFAULT_MODEL}, got {model!r}")
    return model


def _check_base_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"{BASE_URL_ENV} must be an http:// or https:// URL, got {url!r}")
    return url.rstrip("/")


def _content(raw: bytes) -> str | None:
    try:
        message = json.loads(raw)["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError):
        return None
    text = message.get("content") if isinstance(message, dict) else None
    if not isinstance(text, str):
        return None
    return _THINK_RE.sub("", text).strip() or None


class OpenAICompatNarrator:
    name = "openai_compat"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        lang: str | None = None,
        opener: Opener = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        url = base_url if base_url is not None else os.environ.get(BASE_URL_ENV)
        if not url:
            raise MissingSettingError(BASE_URL_ENV)
        self.base_url = _check_base_url(url)
        self.llm_model = _check_model(model) if model is not None else configured_model()
        self._api_key = api_key if api_key is not None else (os.environ.get(API_KEY_ENV) or None)
        self.lang = lang if lang is not None else commentary_lang()
        self._opener = opener
        self._sleep = sleep
        # Last error seen by narrate(), for the command's failure report.
        self.last_error: Exception | None = None

    def _request(self, prompt: str) -> urllib.request.Request:
        body = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )

    def _post(self, request: urllib.request.Request) -> bytes:
        with self._opener(request, timeout=TIMEOUT_S) as response:
            return response.read()

    def narrate(self, event: Mapping[str, Any]) -> str | None:
        request = self._request(build_prompt(event, self.lang))
        raw, self.last_error = call_with_retries(lambda: self._post(request), self._sleep)
        return _content(raw) if raw is not None else None


register(OpenAICompatNarrator.name, OpenAICompatNarrator)
