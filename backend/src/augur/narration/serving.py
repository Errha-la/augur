"""Which cached commentary the API serves: the current narrator settings.

Read from the environment (and the settings' commentary language) only;
building the key never needs an API key or a reachable LLM server.
"""

from __future__ import annotations

from collections.abc import Callable

from augur.narration import gemini, openai_compat
from augur.narration.base import selected_narrator_name
from augur.narration.cache import CommentaryKey
from augur.narration.prompt import PROMPT_VERSION, check_lang, commentary_lang

# Configured model name per narrator, read without building the narrator.
_CONFIGURED_MODEL: dict[str, Callable[[], str]] = {
    gemini.GeminiNarrator.name: gemini.configured_model,
    openai_compat.OpenAICompatNarrator.name: openai_compat.configured_model,
}


def configured_llm_model(narrator: str) -> str | None:
    """The configured LLM model name for ``narrator``; None when unknown or invalid."""
    configured = _CONFIGURED_MODEL.get(narrator)
    if configured is None:
        return None
    try:
        return configured()
    except ValueError:
        return None


def serving_key(model: str, lang: str | None = None) -> CommentaryKey | None:
    """Cache key for the served model under the current settings.

    ``lang`` is the settings' commentary language (default: $AUGUR_COMMENTARY_LANG).
    None when the narrator is ``none``, has no known configured model, or any
    setting is invalid: the API then serves no commentary instead of failing.
    """
    try:
        name = selected_narrator_name()
        llm_model = configured_llm_model(name)
        if llm_model is None:
            return None
        language = check_lang(lang) if lang is not None else commentary_lang()
        return CommentaryKey(model, name, llm_model, language, PROMPT_VERSION)
    except ValueError:
        return None
