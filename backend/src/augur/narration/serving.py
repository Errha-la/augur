"""Which cached commentary the API serves: the current narrator settings.

Read from the environment only; building the key never needs an API key or a
reachable LLM server.
"""

from __future__ import annotations

from collections.abc import Callable

from augur.narration import gemini, openai_compat
from augur.narration.base import selected_narrator_name
from augur.narration.cache import CommentaryKey
from augur.narration.prompt import PROMPT_VERSION, commentary_lang

# Configured model name per narrator, read without building the narrator.
_CONFIGURED_MODEL: dict[str, Callable[[], str]] = {
    gemini.GeminiNarrator.name: gemini.configured_model,
    openai_compat.OpenAICompatNarrator.name: openai_compat.configured_model,
}


def serving_key(model: str) -> CommentaryKey | None:
    """Cache key for the served model under the current settings.

    None when the narrator is ``none``, has no known configured model, or any
    setting is invalid: the API then serves no commentary instead of failing.
    """
    try:
        name = selected_narrator_name()
        configured = _CONFIGURED_MODEL.get(name)
        if configured is None:
            return None
        return CommentaryKey(model, name, configured(), commentary_lang(), PROMPT_VERSION)
    except ValueError:
        return None
