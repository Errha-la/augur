"""Decide whether undercut and degradation calls came true.

Outcomes are resolved at analyze time from the whole race (they are about the
future by definition) and stored with the lap that decided them; the API
reveals them only once the replay reaches that lap.

Rules (window ``config.OUTCOME_WINDOW_LAPS`` = W):

- ``undercut_window`` at lap E, chaser C behind target T: "hit" when C's
  computed position is ahead of T at lap E+W, "miss" otherwise, "void" when
  the race has fewer than E+W laps. Decided on lap E+W (void: ``total_laps``).
- ``degradation_warning`` at lap E for driver D: "hit" when D has a ``pit_in``
  lap P with E < P <= E+W (decided on P), "miss" when D completes lap E+W
  without one (decided on E+W), "void" when the race has fewer than E+W laps
  and D did not pit, or D stopped before lap E+W (decided on ``total_laps``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

import pandas as pd

from augur import config
from augur.state import race_state

OUTCOME_FIELDS: tuple[str, ...] = ("outcome", "outcome_lap", "outcome_text")
OUTCOME_TYPES = frozenset({"undercut_window", "degradation_warning"})

NO_OUTCOME: dict[str, Any] = {"outcome": None, "outcome_lap": None, "outcome_text": None}


def _result(outcome: str, lap: int, text: str) -> dict[str, Any]:
    return {"outcome": outcome, "outcome_lap": int(lap), "outcome_text": text}


def undercut_outcome(
    lap: int, chaser: str, target: str, total_laps: int, position_at: Callable[[int], Mapping[str, int]]
) -> dict[str, Any]:
    decide = lap + config.OUTCOME_WINDOW_LAPS
    if decide > total_laps:
        return _result(
            "void",
            total_laps,
            f"The race ended on lap {total_laps}, before lap {decide} could decide {chaser}'s undercut on {target}.",
        )
    positions = position_at(decide)
    c, t = positions.get(chaser), positions.get(target)
    if c is not None and t is not None and c < t:
        return _result("hit", decide, f"{chaser} was ahead of {target} on lap {decide} (P{c} vs P{t}).")
    behind = f" (P{c} vs P{t})" if c is not None and t is not None else ""
    return _result("miss", decide, f"{chaser} was still behind {target} on lap {decide}{behind}.")


def degradation_outcome(
    lap: int, driver: str, total_laps: int, pit_laps: Iterable[int], last_lap: int
) -> dict[str, Any]:
    window = config.OUTCOME_WINDOW_LAPS
    decide = lap + window
    pits = sorted(p for p in pit_laps if lap < p <= decide)
    if pits:
        p = pits[0]
        return _result("hit", p, f"{driver} pitted on lap {p}, {p - lap} laps after the warning.")
    if decide > total_laps:
        return _result(
            "void",
            total_laps,
            f"The race ended on lap {total_laps}, before lap {decide}, without a stop for {driver}.",
        )
    if last_lap < decide:
        return _result("void", total_laps, f"{driver} stopped before lap {decide} without pitting.")
    return _result("miss", decide, f"{driver} did not pit by lap {decide}, {window} laps after the warning.")


def resolve_outcomes(
    events: list[dict], laps: pd.DataFrame, drivers: Iterable[Mapping[str, Any]], race_meta: Mapping[str, Any]
) -> list[dict]:
    """Copies of ``events`` with ``outcome``, ``outcome_lap`` and ``outcome_text`` set.

    ``laps`` are all rows of the race; ``race_meta`` has ``race_id`` and ``total_laps``.
    Event types without a rule get three nulls.
    """
    total = int(race_meta["total_laps"])
    drivers = list(drivers)
    cache: dict[int, dict[str, int]] = {}

    def position_at(n: int) -> dict[str, int]:
        if n not in cache:
            state = race_state(laps[laps["lap"] <= n], drivers, race_meta, n)
            cache[n] = {d["code"]: d["position"] for d in state["drivers"]}
        return cache[n]

    pit_laps: dict[str, list[int]] = {}
    for code, n in zip(laps.loc[laps["pit_in"].fillna(False).astype(bool), "driver"],
                       laps.loc[laps["pit_in"].fillna(False).astype(bool), "lap"]):
        pit_laps.setdefault(code, []).append(int(n))
    last_lap = {code: int(n) for code, n in laps.groupby("driver")["lap"].max().items()}

    out = []
    for e in events:
        ev = e.get("evidence") or {}
        if e["type"] == "undercut_window":
            chaser = ev.get("chaser") or e["drivers"][0]
            target = ev.get("ahead") or e["drivers"][1]
            result = undercut_outcome(e["lap"], chaser, target, total, position_at)
        elif e["type"] == "degradation_warning":
            driver = ev.get("driver") or e["drivers"][0]
            result = degradation_outcome(e["lap"], driver, total, pit_laps.get(driver, []), last_lap.get(driver, 0))
        else:
            result = dict(NO_OUTCOME)
        out.append({**e, **result})
    return out


def visible(event: Mapping[str, Any], lap: int) -> dict[str, Any]:
    """The event's outcome fields as seen at replay lap ``lap``: null until decided."""
    decided = event.get("outcome_lap")
    if event.get("outcome") is None or decided is None or decided > lap:
        return dict(NO_OUTCOME)
    return {k: event.get(k) for k in OUTCOME_FIELDS}
