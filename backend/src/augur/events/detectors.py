"""Rule-based race event detectors.

Each detector is a pure function of what is known at lap N (passed in as
plain values) plus its own dedupe memory, and returns raw events
``{lap, type, drivers, severity, evidence}``. Thresholds live in augur.config.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from augur import config


def _severity(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _event(lap: int, type_: str, drivers: list[str], severity: float, evidence: dict) -> dict:
    return {"lap": lap, "type": type_, "drivers": drivers, "severity": _severity(severity), "evidence": evidence}


@dataclass
class DetectorState:
    """Dedupe memory carried between laps."""

    pace_drop_last: dict[str, int] = field(default_factory=dict)
    deg_fired: set[tuple[str, int]] = field(default_factory=set)
    cliff_fired: set[tuple[str, int]] = field(default_factory=set)
    undercut_fired: set[tuple[str, str, int]] = field(default_factory=set)
    prev_positions: dict[str, int] | None = None


@dataclass(frozen=True)
class LapObservation:
    """A driver's lap N as the pace detector sees it."""

    driver: str
    lap_time_s: float | None
    predicted_s: float | None
    clean: bool
    compound: str | None = None
    tyre_life: int | None = None


def detect_pace_drop(lap: int, observations: Iterable[LapObservation], state: DetectorState) -> list[dict]:
    """Clean lap N more than PACE_DROP_S slower than predicted; once per driver per 3 laps."""
    out = []
    for o in sorted(observations, key=lambda o: o.driver):
        if not o.clean or o.lap_time_s is None or o.predicted_s is None:
            continue
        slower = o.lap_time_s - o.predicted_s
        if slower <= config.PACE_DROP_S:
            continue
        last = state.pace_drop_last.get(o.driver)
        if last is not None and lap - last < config.PACE_DROP_COOLDOWN_LAPS:
            continue
        state.pace_drop_last[o.driver] = lap
        out.append(
            _event(
                lap,
                "pace_drop",
                [o.driver],
                30.0 * slower,
                {
                    "driver": o.driver,
                    "lap_time_s": round(o.lap_time_s, 3),
                    "predicted_s": round(o.predicted_s, 3),
                    "slower_s": round(slower, 3),
                    "compound": o.compound,
                    "tyre_life": o.tyre_life,
                },
            )
        )
    return out


def detect_degradation(lap: int, degradation: Mapping[str, dict], state: DetectorState) -> list[dict]:
    """Stint slope >= 0.10 s/lap over >= 5 clean laps, or a cliff; once per stint (+ once for a cliff)."""
    out = []
    for driver in sorted(degradation):
        d = degradation[driver]
        stint = d.get("stint")
        if stint is None:
            continue
        key = (driver, int(stint))
        slope = d.get("deg_s_per_lap")
        evidence = {
            "driver": driver,
            "stint": int(stint),
            "compound": d.get("compound"),
            "tyre_life": d.get("tyre_life"),
            "deg_s_per_lap": slope,
            "deg_laps": d.get("deg_laps"),
            "cliff": bool(d.get("cliff")),
        }
        if d.get("cliff") and key not in state.cliff_fired:
            state.cliff_fired.add(key)
            state.deg_fired.add(key)
            out.append(_event(lap, "degradation_warning", [driver], 80.0, evidence))
        elif (
            slope is not None
            and slope >= config.DEG_WARNING_S_PER_LAP
            and (d.get("deg_laps") or 0) >= config.DEG_WARNING_MIN_LAPS
            and key not in state.deg_fired
        ):
            state.deg_fired.add(key)
            out.append(_event(lap, "degradation_warning", [driver], 500.0 * slope, evidence))
    return out


@dataclass(frozen=True)
class CarStatus:
    """A car's state after its last completed lap, for the undercut detector."""

    driver: str
    position: int
    laps_completed: int
    session_time_s: float | None
    stint: int | None
    compound: str | None
    tyre_life: int | None
    pitted_recently: bool  # pit in or out within the last UNDERCUT_NO_PIT_LAPS laps
    deg_s_per_lap: float | None = None


def detect_undercut(lap: int, cars: Iterable[CarStatus], state: DetectorState) -> list[dict]:
    """Chaser within 2.5 s of the car directly ahead on the same lap count, car ahead on
    tyres >= 12 laps old, neither pitted in the last 3 laps; once per pair per stint of the car ahead."""
    ordered = sorted(cars, key=lambda c: c.position)
    out = []
    for ahead, chaser in zip(ordered, ordered[1:]):
        if ahead.laps_completed != chaser.laps_completed or ahead.laps_completed < 1:
            continue
        if ahead.session_time_s is None or chaser.session_time_s is None:
            continue
        gap = chaser.session_time_s - ahead.session_time_s
        if not 0.0 <= gap <= config.UNDERCUT_GAP_S:
            continue
        if ahead.tyre_life is None or ahead.tyre_life < config.UNDERCUT_MIN_TYRE_AGE:
            continue
        if ahead.pitted_recently or chaser.pitted_recently or ahead.stint is None:
            continue
        key = (chaser.driver, ahead.driver, ahead.stint)
        if key in state.undercut_fired:
            continue
        state.undercut_fired.add(key)
        out.append(
            _event(
                lap,
                "undercut_window",
                [chaser.driver, ahead.driver],
                60.0,
                {
                    "chaser": chaser.driver,
                    "ahead": ahead.driver,
                    "gap_s": round(gap, 3),
                    "ahead_tyre_life": ahead.tyre_life,
                    "ahead_compound": ahead.compound,
                    "ahead_stint": ahead.stint,
                    "ahead_deg_s_per_lap": ahead.deg_s_per_lap,
                    "chaser_tyre_life": chaser.tyre_life,
                    "chaser_compound": chaser.compound,
                },
            )
        )
    return out


def detect_position_change(
    lap: int, positions: Mapping[str, int], state: DetectorState, total_laps: int
) -> list[dict]:
    """Gain/loss of >= 2 places from lap N-1, or a new leader; never on lap 1."""
    prev = state.prev_positions
    state.prev_positions = dict(positions)
    if lap <= 1 or prev is None:
        return []
    out = []
    remaining = max(0, total_laps - lap)
    old_leader = min(prev, key=prev.get) if prev else None
    new_leader = min(positions, key=positions.get) if positions else None
    if old_leader and new_leader and old_leader != new_leader:
        out.append(
            _event(
                lap,
                "position_change",
                [new_leader, old_leader],
                90.0,
                {
                    "driver": new_leader,
                    "previous_leader": old_leader,
                    "from_position": prev.get(new_leader),
                    "to_position": 1,
                    "places": None if prev.get(new_leader) is None else prev[new_leader] - 1,
                    "leader_change": True,
                    "laps_remaining": remaining,
                },
            )
        )
    for driver in sorted(positions):
        if driver not in prev:
            continue
        places = prev[driver] - positions[driver]  # > 0 gained
        if abs(places) < config.POSITION_CHANGE_MIN_PLACES:
            continue
        out.append(
            _event(
                lap,
                "position_change",
                [driver],
                20.0 * abs(places),
                {
                    "driver": driver,
                    "previous_leader": None,
                    "from_position": prev[driver],
                    "to_position": positions[driver],
                    "places": places,
                    "leader_change": False,
                    "laps_remaining": remaining,
                },
            )
        )
    return out
