"""Number links: which numbers in an event's texts come from which evidence field.

``event_links(event)`` is a pure function of one served event. A number in the
analysis or commentary text is found and compared with the grounding check's
rules (``NUMBER_RE``, ``matches_shown``). A number equal to the event lap gets
no link; otherwise the first field of ``FIELDS`` (in order) whose evidence
value matches it gives the link's field, chart and drivers. Offsets index
Unicode code points (Python ``str`` indexes), ``end`` exclusive.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from augur.narration.grounding import NUMBER_RE, matches_shown

TEXTS = ("what", "why", "next", "commentary")

Drivers = Callable[[Mapping[str, Any], Mapping[str, Any]], list]


def _one(key: str) -> Drivers:
    return lambda ev, event: [ev.get(key)]


def _gap(ev: Mapping[str, Any], event: Mapping[str, Any]) -> list:
    return [ev.get("chaser") or ev.get("driver"), ev.get("ahead")]


def _first_driver(ev: Mapping[str, Any], event: Mapping[str, Any]) -> list:
    return list(event.get("drivers") or [])[:1]


# (evidence field, chart kind, drivers), in matching order (design.md field table).
FIELDS: tuple[tuple[str, str, Drivers], ...] = (
    ("deg_s_per_lap", "degradation", _one("driver")),
    ("deg_laps", "degradation", _one("driver")),
    ("ahead_deg_s_per_lap", "degradation", _one("ahead")),
    ("lap_time_s", "laptimes", _one("driver")),
    ("predicted_s", "laptimes", _one("driver")),
    ("slower_s", "laptimes", _one("driver")),
    ("gap_s", "trace", _gap),
    ("tyre_life", "stints", _one("driver")),
    ("stint", "stints", _one("driver")),
    ("ahead_tyre_life", "stints", _one("ahead")),
    ("ahead_stint", "stints", _one("ahead")),
    ("chaser_tyre_life", "stints", _one("chaser")),
    ("strategy.pit_lap", "pitwindow", _first_driver),
    ("strategy.win_probability", "pitwindow", _first_driver),
    ("from_position", "positions", _one("driver")),
    ("to_position", "positions", _one("driver")),
    ("places", "positions", _one("driver")),
    ("laps_remaining", "positions", _one("driver")),
)


def _value(evidence: Mapping[str, Any], field: str) -> float | None:
    value: Any = evidence
    for part in field.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return abs(float(value))


def _links(text: Any, lap: Any, fields: list[tuple[str, str, list[str], float]]) -> list[dict]:
    if not isinstance(text, str) or not text:
        return []
    has_lap = isinstance(lap, int) and not isinstance(lap, bool)
    out: list[dict] = []
    for m in NUMBER_RE.finditer(text):
        shown, percent = m.group(1), bool(m.group(2))
        if has_lap and matches_shown(shown, float(lap), percent):
            continue
        for field, chart, drivers, value in fields:
            if matches_shown(shown, value, percent):
                # The regex may take whitespace after the number; the span is the number and its %.
                end = m.end(2) if percent else m.end(1)
                out.append({"start": m.start(1), "end": end, "field": field, "chart": chart,
                            "drivers": list(drivers)})
                break
    return out


def event_links(event: Mapping[str, Any]) -> dict[str, list[dict]]:
    """``{what, why, next, commentary}`` link lists for one served event."""
    evidence = event.get("evidence") or {}
    fields = []
    for field, chart, who in FIELDS:
        value = _value(evidence, field)
        if value is None:
            continue
        drivers = [d for d in who(evidence, event) if isinstance(d, str) and d]
        fields.append((field, chart, drivers, value))
    analysis = event.get("analysis") or {}
    texts = {"what": analysis.get("what"), "why": analysis.get("why"), "next": analysis.get("next"),
             "commentary": event.get("commentary")}
    lap = event.get("lap")
    return {key: _links(texts[key], lap, fields) for key in TEXTS}
