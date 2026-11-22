"""Runtime settings: served model, commentary language, data source.

Precedence per field: ``data/settings.json`` > environment variable > default.
Read on every request, so a change applies without a restart. The commentary
narrator and every key or LLM server address stay in the server environment;
the API reports only a read-only status for them.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from augur import config
from augur.models import registry
from augur.narration.base import DEFAULT_NARRATOR, NARRATOR_ENV, NoneNarrator
from augur.narration.gemini import API_KEY_ENV as GEMINI_KEY_ENV
from augur.narration.openai_compat import BASE_URL_ENV
from augur.narration.prompt import DEFAULT_LANG, LANG_ENV, SUPPORTED_LANGS
from augur.narration.serving import configured_llm_model

SETTINGS_FILE = "settings.json"
FIELDS: tuple[str, ...] = ("model", "commentary_lang", "data_source")
DATA_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "replay", "available": True},
    {"name": "live", "available": False},
)
_ENV = {"model": config.MODEL_ENV, "commentary_lang": LANG_ENV}
_DEFAULTS = {"model": config.DEFAULT_MODEL, "commentary_lang": DEFAULT_LANG, "data_source": "replay"}
# The environment variable each narrator needs before it can generate commentary.
_REQUIRED = {"gemini": GEMINI_KEY_ENV, "openai_compat": BASE_URL_ENV}


@dataclass(frozen=True)
class Settings:
    model: str
    commentary_lang: str
    data_source: str


class SettingsError(ValueError):
    """A rejected settings update; the message is the API's 422 ``detail``."""


def settings_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / SETTINGS_FILE


def _stored(data_dir: Path | str) -> dict[str, str]:
    try:
        raw = json.loads(settings_path(data_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}  # no file yet, or a broken one: fall back to environment and defaults
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k in FIELDS and isinstance(v, str) and v}


def current(data_dir: Path | str) -> Settings:
    stored = _stored(data_dir)
    values = {
        field: stored.get(field) or (os.environ.get(_ENV[field]) if field in _ENV else None) or _DEFAULTS[field]
        for field in FIELDS
    }
    return Settings(**values)


def _check(data_dir: Path | str, field: str, value: Any) -> None:
    if field == "model":
        if not isinstance(value, str) or value not in registry.model_names():
            raise SettingsError(f"unknown model {value}")
        if not registry.model_path(data_dir, value).is_file():
            raise SettingsError(f"model {value} is not trained")
    elif field == "commentary_lang":
        if value not in SUPPORTED_LANGS:
            raise SettingsError(f"unsupported language {value}")
    elif field == "data_source":
        if value == "live":
            raise SettingsError("live data is not available yet")
        if value != "replay":
            raise SettingsError(f"unknown data source {value}")


def update(data_dir: Path | str, body: Any) -> Settings:
    """Validate every field first, then merge into data/settings.json (nothing is written on error)."""
    if not isinstance(body, dict):
        raise SettingsError("settings must be a JSON object")
    for field in body:
        if field not in FIELDS:
            raise SettingsError(f"unknown field {field}")
    for field, value in body.items():
        _check(data_dir, field, value)
    merged = {**_stored(data_dir), **body}
    path = settings_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)  # atomic: a reader never sees a half-written file
    return current(data_dir)


def commentary_status() -> dict[str, Any]:
    """Read-only narrator status: names of settings only, never their values."""
    narrator = os.environ.get(NARRATOR_ENV) or DEFAULT_NARRATOR
    if narrator == NoneNarrator.name:
        return {"narrator": narrator, "llm_model": None, "configured": False, "missing": None}
    required = _REQUIRED.get(narrator)
    missing = required if required is not None and not os.environ.get(required) else None
    return {
        "narrator": narrator,
        "llm_model": configured_llm_model(narrator),
        "configured": required is not None and missing is None,
        "missing": missing,
    }


def describe(data_dir: Path | str) -> dict[str, Any]:
    """The GET /api/settings body."""
    models = []
    for name in registry.model_names():
        models.append(
            {
                "name": name,
                "author": getattr(registry.get_model_class(name), "author", None),
                "trained": registry.model_path(data_dir, name).is_file(),
            }
        )
    return {
        **asdict(current(data_dir)),
        "models": models,
        "commentary_langs": list(SUPPORTED_LANGS),
        "data_sources": [dict(s) for s in DATA_SOURCES],
        "commentary": commentary_status(),
    }
