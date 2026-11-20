"""Optional LLM commentary for race events (llm-commentary)."""

from augur.narration.base import (
    Narrator,
    NoneNarrator,
    UnknownNarratorError,
    get_narrator,
    narrator_names,
    register,
)
from augur.narration.prompt import (
    DEFAULT_LANG,
    LANG_ENV,
    PROMPT_VERSION,
    SUPPORTED_LANGS,
    build_prompt,
    commentary_lang,
)
from augur.narration.grounding import Grounding, check_grounding
from augur.narration.gemini import GeminiNarrator, MissingApiKeyError  # registers "gemini"
from augur.narration.openai_compat import OpenAICompatNarrator  # registers "openai_compat"
from augur.narration.base import MissingSettingError

__all__ = [
    "GeminiNarrator",
    "MissingSettingError",
    "OpenAICompatNarrator",
    "Grounding",
    "MissingApiKeyError",
    "check_grounding",
    "DEFAULT_LANG",
    "LANG_ENV",
    "PROMPT_VERSION",
    "SUPPORTED_LANGS",
    "Narrator",
    "NoneNarrator",
    "UnknownNarratorError",
    "build_prompt",
    "commentary_lang",
    "get_narrator",
    "narrator_names",
    "register",
]
