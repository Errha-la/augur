"""Gemini narrator through the google-genai SDK.

Optional: google-genai is imported only when a real client is built, so tests
and offline use never need the package or an API key.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Mapping
from typing import Any

from augur.narration.base import RETRY_WAITS_S, MissingSettingError, call_with_retries, register
from augur.narration.prompt import build_prompt, commentary_lang

__all__ = [
    "API_KEY_ENV",
    "DEFAULT_MODEL",
    "MAX_OUTPUT_TOKENS",
    "MODEL_ENV",
    "RETRY_WAITS_S",
    "TEMPERATURE",
    "GeminiNarrator",
    "MissingApiKeyError",
    "configured_model",
]

API_KEY_ENV = "GEMINI_API_KEY"
MODEL_ENV = "GEMINI_MODEL"
DEFAULT_MODEL = "gemini-flash-latest"
TEMPERATURE = 0.4
MAX_OUTPUT_TOKENS = 200

MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{0,63}$")


class MissingApiKeyError(MissingSettingError):
    def __init__(self) -> None:
        super().__init__(API_KEY_ENV)


def configured_model() -> str:
    """$GEMINI_MODEL (unset or empty: gemini-flash-latest), validated."""
    model = os.environ.get(MODEL_ENV) or DEFAULT_MODEL
    if not MODEL_RE.fullmatch(model):
        raise ValueError(f"{MODEL_ENV} must be a model id like {DEFAULT_MODEL}, got {model!r}")
    return model


def _real_client() -> Any:
    key = os.environ.get(API_KEY_ENV)
    if not key:
        raise MissingApiKeyError()
    from google import genai

    return genai.Client(api_key=key)


class GeminiNarrator:
    name = "gemini"

    def __init__(
        self,
        client: Any | None = None,
        model: str | None = None,
        lang: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.llm_model = model if model is not None else configured_model()
        self.lang = lang if lang is not None else commentary_lang()
        self._client = client if client is not None else _real_client()
        self._sleep = sleep
        # Last error seen by narrate(), for the command's failure report.
        self.last_error: Exception | None = None

    def narrate(self, event: Mapping[str, Any]) -> str | None:
        prompt = build_prompt(event, self.lang)
        config = {"temperature": TEMPERATURE, "max_output_tokens": MAX_OUTPUT_TOKENS}
        response, self.last_error = call_with_retries(
            lambda: self._client.models.generate_content(model=self.llm_model, contents=prompt, config=config),
            self._sleep,
        )
        if response is None:
            return None
        text = (getattr(response, "text", None) or "").strip()
        return text or None


register(GeminiNarrator.name, GeminiNarrator)
