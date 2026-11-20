"""Narrator protocol, the offline ``none`` narrator, and the narrator registry.

A narrator turns one analyzed event into optional commentary text. The
template analysis stays the source of truth; commentary is an extra field,
so every narrator may return None.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


@runtime_checkable
class Narrator(Protocol):
    name: str

    def narrate(self, event: Mapping[str, Any]) -> str | None: ...


class NoneNarrator:
    """Offline default: never produces commentary."""

    name = "none"

    def narrate(self, event: Mapping[str, Any]) -> str | None:
        return None


class MissingSettingError(RuntimeError):
    """A narrator's required environment variable is unset; ``augur.narrate`` exits 0."""

    def __init__(self, setting: str) -> None:
        super().__init__(f"{setting} not set")
        self.setting = setting


# Waits before the two retries on HTTP 429 or 5xx.
RETRY_WAITS_S: tuple[float, ...] = (2.0, 4.0)


def is_retryable(exc: BaseException) -> bool:
    """HTTP 429 or 5xx, read from the exception's ``code``."""
    code = getattr(exc, "code", None)
    return isinstance(code, int) and (code == 429 or 500 <= code <= 599)


def call_with_retries(call: Callable[[], T], sleep: Callable[[float], None]) -> tuple[T | None, Exception | None]:
    """(result, None) on success, else (None, last error) after retrying 429/5xx twice."""
    for attempt in range(len(RETRY_WAITS_S) + 1):
        try:
            return call(), None
        except Exception as exc:  # SDK, network, or HTTP errors: the event gets no commentary
            if attempt < len(RETRY_WAITS_S) and is_retryable(exc):
                sleep(RETRY_WAITS_S[attempt])
                continue
            return None, exc
    raise AssertionError("unreachable")


class UnknownNarratorError(LookupError):
    def __init__(self, name: object) -> None:
        super().__init__(f"unknown narrator {name}")
        self.name = name

    def __str__(self) -> str:
        return self.args[0]


_REGISTRY: dict[str, Callable[[], Narrator]] = {}


def register(name: str, factory: Callable[[], Narrator]) -> None:
    """Register a zero-argument narrator factory under ``name``."""
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ValueError(f"narrator name must match {NAME_RE.pattern}, got {name!r}")
    if not callable(factory):
        raise ValueError(f"narrator {name} needs a callable factory")
    if name in _REGISTRY and _REGISTRY[name] is not factory:
        raise ValueError(f"narrator {name} is already registered")
    _REGISTRY[name] = factory


def narrator_names() -> list[str]:
    return sorted(_REGISTRY)


NARRATOR_ENV = "AUGUR_NARRATOR"
DEFAULT_NARRATOR = "gemini"


def selected_narrator_name() -> str:
    """$AUGUR_NARRATOR (unset or empty: gemini); an unknown name fails loudly."""
    name = os.environ.get(NARRATOR_ENV) or DEFAULT_NARRATOR
    if name not in _REGISTRY:
        raise ValueError(f"{NARRATOR_ENV} must be one of {', '.join(narrator_names())}, got {name!r}")
    return name


def get_narrator(name: str) -> Narrator:
    factory = _REGISTRY.get(name)
    if factory is None:
        raise UnknownNarratorError(name)
    return factory()


register(NoneNarrator.name, NoneNarrator)
