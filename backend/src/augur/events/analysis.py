"""Deterministic What / Why / Next text for race events.

Voice: an analyst explaining the race to fans. ``next`` is a conditional,
probabilistic outlook, never an instruction to the team or driver. Every
sentence is filled only from the event's evidence, so equal inputs give
equal text.
"""

from __future__ import annotations

from augur import config


def _pct(probability: float) -> int:
    return int(round(float(probability) * 100))


def strategy_outlook(driver: str, strategy: dict | None, rival: str | None = None) -> str:
    if not strategy:
        return f"The strategy comparison for {driver} needs more clean laps before it can favour an option."
    if strategy.get("pit_lap") is None:
        option = "Running to the finish without another stop"
    else:
        option = f"Pitting on lap {strategy['pit_lap']}"
    tail = f", which would put pressure on {rival}." if rival else "."
    return f"{option} is {driver}'s fastest option in {_pct(strategy['win_probability'])}% of simulations{tail}"


def _pace_drop(lap: int, ev: dict) -> tuple[str, dict]:
    d = ev["driver"]
    tyres = ""
    if ev.get("tyre_life") is not None and ev.get("compound"):
        tyres = f" on {ev['tyre_life']}-lap-old {ev['compound']} tyres"
    return f"{d} loses pace on lap {lap}", {
        "what": (
            f"{d} lapped in {ev['lap_time_s']:.3f} s on lap {lap}, "
            f"{ev['slower_s']:.1f} s slower than the predicted {ev['predicted_s']:.3f} s."
        ),
        "why": (
            f"The prediction comes from {d}'s recent clean-lap pace{tyres}, so a gap this large "
            "points to traffic, a mistake, or grip fading faster than expected."
        ),
        "next": f"If the next laps stay this slow, {d} is likely to lose time to nearby cars.",
    }


def _degradation(lap: int, ev: dict) -> tuple[str, dict]:
    d = ev["driver"]
    compound = ev.get("compound") or "current"
    slope = ev.get("deg_s_per_lap")
    if ev.get("cliff"):
        title = f"{d}'s {compound} tyres hit a performance cliff"
        what = (
            f"{d}'s last two clean laps up to lap {lap} were more than "
            f"{config.CLIFF_RESIDUAL_S:g} s slower than the stint's trend."
        )
    else:
        title = f"{d}'s {compound} tyres are fading"
        what = (
            f"{d} is losing {slope:.3f} s per lap on {compound} tyres "
            f"over {ev['deg_laps']} clean laps of stint {ev['stint']}."
        )
    age = f"{ev['tyre_life']} laps old" if ev.get("tyre_life") is not None else "of unknown age"
    if slope is not None:
        why = f"The tyres are {age}, and the stint's fuel-corrected lap times rise by {slope:.3f} s per lap."
    else:
        why = f"The tyres are {age}, and the latest laps sit well above the stint's earlier trend."
    return title, {"what": what, "why": why, "next": strategy_outlook(d, ev.get("strategy"))}


def _undercut(lap: int, ev: dict) -> tuple[str, dict]:
    c, a = ev["chaser"], ev["ahead"]
    compound = ev.get("ahead_compound") or "current"
    slope = ev.get("ahead_deg_s_per_lap")
    loss = f"losing {slope:.3f} s per lap" if slope is not None else "with degradation not yet measurable"
    return f"Undercut window: {c} on {a}", {
        "what": f"{c} is {ev['gap_s']:.1f} s behind {a} on lap {lap}.",
        "why": f"{a}'s {compound} tyres are {ev['ahead_tyre_life']} laps old and {loss}, so fresh tyres could gain time quickly.",
        "next": strategy_outlook(c, ev.get("strategy"), rival=a),
    }


def _overcut(lap: int, ev: dict) -> tuple[str, dict]:
    d, a = ev["driver"], ev["ahead"]
    compound = ev.get("compound") or "current"
    deg = ev["deg_s_per_lap"]
    # A negative fit means lap times are still falling (fuel burn outpaces tyre wear).
    wear = (
        f"are losing only {deg:.3f} s per lap"
        if deg > 0
        else f"are not losing time yet (lap times falling {abs(deg):.3f} s per lap)"
    )
    return f"Overcut window: {d} on {a}", {
        "what": f"{a} pitted on lap {lap} with {d} {ev['gap_s']:.1f} s behind on lap {lap - 1}.",
        "why": f"{d}'s {compound} tyres {wear}, so laps in clear air while {a} completes its stop could gain time.",
        "next": strategy_outlook(d, ev.get("strategy"), rival=a),
    }


def _position_change(lap: int, ev: dict) -> tuple[str, dict]:
    d = ev["driver"]
    pits = list(ev.get("pit_drivers") or [])
    remaining = ev.get("laps_remaining", 0)
    if ev.get("leader_change"):
        old = ev["previous_leader"]
        title = f"{d} takes the lead"
        what = f"{d} took the lead from {old} on lap {lap}."
        if old in pits:
            why = f"{old} was in the pit lane on this lap."
        elif d in pits:
            why = f"{d} gained the lead around a pit stop on this lap."
        else:
            why = f"Neither {d} nor {old} pitted on this lap, so the change happened on track."
        position = 1
    else:
        places = ev["places"]
        verb = "moved up" if places > 0 else "dropped"
        title = f"{d} {verb} {abs(places)} places"
        what = f"{d} {verb} from P{ev['from_position']} to P{ev['to_position']} on lap {lap}."
        others = [p for p in pits if p != d]
        if d in pits:
            why = f"{d} made a pit stop on this lap."
        elif others:
            why = f"{d} changed places while {', '.join(others)} made pit stops."
        else:
            why = "No pit stop explains it, so the change happened on track."
        position = ev["to_position"]
    if remaining > 0:
        nxt = (
            f"With {remaining} laps remaining, P{position} is provisional for {d}; "
            "pit cycles and pace over the next laps decide whether it holds."
        )
    else:
        nxt = f"The change came on the final lap, so P{position} is where {d} crosses the line."
    return title, {"what": what, "why": why, "next": nxt}


_TEMPLATES = {
    "pace_drop": _pace_drop,
    "degradation_warning": _degradation,
    "undercut_window": _undercut,
    "overcut_window": _overcut,
    "position_change": _position_change,
}


def explain(event: dict) -> tuple[str, dict]:
    """(title, {what, why, next}) for an event with ``lap``, ``type``, ``evidence``."""
    return _TEMPLATES[event["type"]](event["lap"], event["evidence"])
