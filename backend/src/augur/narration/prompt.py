"""Prompt builder for LLM commentary.

The prompt is built from an allowlist of event fields (type, lap, drivers,
evidence, template analysis), so outcome fields never reach the model.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from augur.events.outcomes import OUTCOME_FIELDS

LANG_ENV = "AUGUR_COMMENTARY_LANG"
DEFAULT_LANG = "en"
# Bump when the prompt text changes so cached commentary is regenerated.
PROMPT_VERSION = 1

_LANG_INSTRUCTIONS: dict[str, str] = {
    "en": "Write in English, at most 60 words.",
    "zh-TW": "Write in Traditional Chinese (Taiwan), at most 120 characters. Keep driver codes as given.",
}
SUPPORTED_LANGS: tuple[str, ...] = tuple(_LANG_INSTRUCTIONS)


def _check_lang(lang: str) -> str:
    if lang not in _LANG_INSTRUCTIONS:
        raise ValueError(f"{LANG_ENV} must be one of {', '.join(SUPPORTED_LANGS)}, got {lang!r}")
    return lang


def commentary_lang() -> str:
    """Commentary language from $AUGUR_COMMENTARY_LANG (unset or empty: en)."""
    return _check_lang(os.environ.get(LANG_ENV) or DEFAULT_LANG)


def _contains_outcome_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(k in OUTCOME_FIELDS or _contains_outcome_key(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_outcome_key(v) for v in value)
    return False


def build_prompt(event: Mapping[str, Any], lang: str) -> str:
    """Prompt for one event; never includes outcome, outcome_lap or outcome_text."""
    _check_lang(lang)
    evidence = event["evidence"]
    if _contains_outcome_key(evidence):
        raise ValueError("event evidence must not contain outcome fields")
    analysis = event["analysis"]
    evidence_json = json.dumps(evidence, sort_keys=True, ensure_ascii=False, default=str)
    return "\n".join(
        [
            "You are a Formula 1 race analyst writing a short comment for fans watching a race replay.",
            "Rewrite the event below as one commentator-style paragraph.",
            "Rules:",
            "- Use only the numbers and driver codes that appear in the event data. Do not add new numbers, drivers, or facts.",
            "- Keep the tone conditional and probabilistic. Do not present any result as certain.",
            "- Do not give instructions to teams or drivers.",
            f"- {_LANG_INSTRUCTIONS[lang]}",
            "",
            f"Event type: {event['type']}",
            f"Lap: {event['lap']}",
            f"Drivers: {', '.join(event['drivers'])}",
            f"Evidence: {evidence_json}",
            f"What: {analysis['what']}",
            f"Why: {analysis['why']}",
            f"Next: {analysis['next']}",
        ]
    )
