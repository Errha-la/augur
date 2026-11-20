"""Grounding check: keep generated commentary only if it invents nothing.

Every number in the text must match the event's lap or a number in the event's
evidence or template text at the precision the text shows (a percentage also matches its
fraction, 62% ~ 0.62), and every three-letter uppercase code must be one of
the event's drivers or a string in its evidence. Numbers written as words
("three") are not detected.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

# A number not glued to a preceding digit or dot, with an optional % sign.
_NUMBER_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*([%％])?")
# Three uppercase letters not inside a longer Latin word (works next to CJK text).
_CODE_RE = re.compile(r"(?<![A-Za-z])[A-Z]{3}(?![A-Za-z])")


@dataclass(frozen=True)
class Grounding:
    accepted: bool
    reason: str | None = None


def _walk(value: Any) -> Iterator[Any]:
    if isinstance(value, Mapping):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _walk(v)
    else:
        yield value


def _source_numbers(event: Mapping[str, Any]) -> list[float]:
    # The lap is in the prompt, and some templates do not repeat it.
    lap = event.get("lap")
    numbers: list[float] = [float(lap)] if isinstance(lap, int) and not isinstance(lap, bool) else []
    for value in _walk(event.get("evidence", {})):
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            numbers.append(abs(float(value)))
        elif isinstance(value, str):
            numbers.extend(float(m.group(1)) for m in _NUMBER_RE.finditer(value))
    for text in (event.get("analysis") or {}).values():
        if isinstance(text, str):
            for m in _NUMBER_RE.finditer(text):
                n = float(m.group(1))
                # "62%" in the template grounds both 62% and 0.62 in the text.
                numbers.append(n / 100 if m.group(2) else n)
    return numbers


def _source_codes(event: Mapping[str, Any]) -> set[str]:
    codes = set(event.get("drivers", []))
    for value in _walk(event.get("evidence", {})):
        if isinstance(value, str):
            codes.update(_CODE_RE.findall(value))
    return codes


def _matches(shown: str, value: float) -> bool:
    """``value`` rounds to ``shown`` at its precision, either way at the half (1.25 -> 1.2 or 1.3)."""
    decimals = len(shown.split(".")[1]) if "." in shown else 0
    return abs(value - float(shown)) <= 0.5 * 10**-decimals + 1e-9


def check_grounding(text: str, event: Mapping[str, Any]) -> Grounding:
    """Accepted only when every number and driver code in ``text`` comes from ``event``."""
    if not text or not text.strip():
        return Grounding(False, "empty text")
    numbers = _source_numbers(event)
    for m in _NUMBER_RE.finditer(text):
        shown, percent = m.group(1), m.group(2)
        if percent:
            # 62% must match a fraction 0.62 (value * 100 at the shown precision).
            ok = any(_matches(shown, v * 100) for v in numbers)
        else:
            ok = any(_matches(shown, v) for v in numbers)
        if not ok:
            label = f"{shown}%" if percent else shown
            return Grounding(False, f"number {label} not in evidence")
    codes = _source_codes(event)
    for code in _CODE_RE.findall(text):
        if code not in codes:
            return Grounding(False, f"driver {code} not in event")
    return Grounding(True)
