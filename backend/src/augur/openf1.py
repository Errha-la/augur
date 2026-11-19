"""OpenF1 REST client, round resolution, and lap normalization.

Data source: the public OpenF1 API (https://api.openf1.org/v1), no account
needed for historical sessions. Only the endpoints in ENDPOINTS are ever
requested (never `session_result` or `starting_grid`).

Responses are cached as JSON lists under `<data_dir>/openf1-cache/`:
    <year>/sessions.json, <year>/meetings.json      (filtered by year)
    <session_key>/<endpoint>.json                   (filtered by session_key)
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from augur import catalog
from augur.schema import DEFAULT_TEAM_COLOR, LAP_COLUMNS
from augur.storage import DriverRecord

BASE_URL = "https://api.openf1.org/v1"
TIMEOUT_S = 60.0
MAX_REQUESTS_PER_SECOND = 3
RETRY_WAITS_S: tuple[float, ...] = (2.0, 4.0, 8.0)

YEAR_ENDPOINTS = frozenset({"sessions", "meetings"})
# Year-level requests take fixed filters only, so each cache file maps to exactly one query.
YEAR_QUERIES: dict[str, tuple[dict[str, str], str]] = {
    "sessions": ({"session_name": "Race"}, "race-sessions.json"),
    "meetings": ({}, "meetings.json"),
}
# OpenF1 answers a query with no rows with HTTP 404 and this detail.
NO_RESULTS_DETAIL = "No results found."
SESSION_ENDPOINTS: tuple[str, ...] = ("drivers", "laps", "stints", "pit", "race_control")
ENDPOINTS = YEAR_ENDPOINTS | frozenset(SESSION_ENDPOINTS)

# Fields each payload row must carry (values may be null where noted in the
# design; a missing key means the API changed and raises KeyError).
LAP_FIELDS = ("driver_number", "lap_number", "date_start", "lap_duration", "is_pit_out_lap")
STINT_FIELDS = ("driver_number", "stint_number", "lap_start", "lap_end", "compound", "tyre_age_at_start")
PIT_FIELDS = ("driver_number", "lap_number")
DRIVER_FIELDS = ("driver_number", "name_acronym", "full_name", "team_name", "team_colour")
RACE_CONTROL_FIELDS = ("date", "category", "flag", "scope", "sector", "message")
SESSION_FIELDS = ("session_key", "meeting_key", "date_start", "location", "is_cancelled")
MEETING_FIELDS = ("meeting_key", "meeting_name")

_HEX6 = re.compile(r"^[0-9A-Fa-f]{6}$")


class OpenF1Error(RuntimeError):
    """An OpenF1 request failed or returned an unusable payload."""


# =============================================================== normalization

# F1 timing track status codes (design.md) and their severity rank (higher = more severe).
GREEN, YELLOW, SAFETY_CAR, RED, VSC = "1", "2", "4", "5", "6"
SEVERITY: dict[str, int] = {GREEN: 0, YELLOW: 1, VSC: 2, SAFETY_CAR: 3, RED: 4}


def _require(rows: Iterable[Mapping[str, Any]], fields: Sequence[str], what: str) -> list[Mapping[str, Any]]:
    """Every row must be a mapping containing every field; else KeyError naming them."""
    if not isinstance(rows, list):
        raise TypeError(f"OpenF1 {what} payload must be a list, got {type(rows).__name__}")
    missing: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError(f"OpenF1 {what} row must be an object, got {type(row).__name__}")
        for field in fields:
            if field not in row and field not in missing:
                missing.append(field)
    if missing:
        raise KeyError(f"OpenF1 {what} missing field(s): {', '.join(missing)}")
    return rows


def _int(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
        raise ValueError(f"{what} must be an integer, got {value!r}")
    return int(value)


def _opt_int(value: Any, what: str) -> int | None:
    return None if value is None else _int(value, what)


def _opt_float(value: Any, what: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{what} must be a number, got {value!r}")
    return float(value)


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_time(value: Any, what: str) -> datetime:
    """ISO 8601 timestamp -> aware UTC datetime (naive input is taken as UTC)."""
    if not isinstance(value, str):
        raise ValueError(f"{what} must be an ISO timestamp, got {value!r}")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{what} is not an ISO timestamp: {value!r}") from exc
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _opt_time(value: Any, what: str) -> datetime | None:
    return None if value is None else parse_time(value, what)


def team_color(value: Any) -> str:
    """OpenF1 team_colour ('3671c6', maybe '#'-prefixed/empty/null) -> '#RRGGBB'."""
    if not isinstance(value, str):
        return DEFAULT_TEAM_COLOR
    text = value.strip().lstrip("#")
    return f"#{text.upper()}" if _HEX6.fullmatch(text) else DEFAULT_TEAM_COLOR


def normalize_compound(value: Any) -> str | None:
    text = _opt_str(value)
    if text is None or text.upper() == "UNKNOWN":
        return None
    return text


# ------------------------------------------------------------- track status


@dataclass(frozen=True)
class _StatusChange:
    at: datetime
    code: str  # most severe status active from `at` until the next change


def track_status_timeline(race_control: list[Mapping[str, Any]]) -> list[_StatusChange]:
    """Replay race control messages (date order) into a list of status changes.

    Rules (design.md "track_status derivation"):
      Flag RED scope Track                      -> red flag starts
      SafetyCar '... VIRTUAL SAFETY CAR DEPLOYED' -> VSC starts
      SafetyCar '... VIRTUAL SAFETY CAR ENDING'   -> VSC ends
      SafetyCar 'SAFETY CAR DEPLOYED' w/o VIRTUAL -> safety car starts
      Flag YELLOW / DOUBLE YELLOW scope Sector  -> yellow in that sector
      Flag CLEAR scope Sector                   -> that sector's yellow ends
      Flag GREEN / CLEAR scope Track            -> red, SC, all yellows end
    """
    _require(race_control, RACE_CONTROL_FIELDS, "race_control")
    messages = sorted(
        ((parse_time(m["date"], "race_control.date"), i, m) for i, m in enumerate(race_control)),
        key=lambda t: (t[0], t[1]),
    )
    red = sc = vsc = False
    yellow_sectors: set[Any] = set()
    timeline: list[_StatusChange] = []
    for at, _, m in messages:
        category = m["category"]
        flag = (m["flag"] or "").upper()
        scope = (m["scope"] or "").upper()
        text = (m["message"] or "").upper()
        if category == "Flag":
            if flag == "RED" and scope == "TRACK":
                red = True
            elif flag in ("YELLOW", "DOUBLE YELLOW") and scope == "SECTOR":
                yellow_sectors.add(m["sector"])
            elif flag == "CLEAR" and scope == "SECTOR":
                yellow_sectors.discard(m["sector"])
            elif flag in ("GREEN", "CLEAR") and scope == "TRACK":
                red = sc = False
                yellow_sectors.clear()
            else:
                continue
        elif category == "SafetyCar":
            if "VIRTUAL SAFETY CAR DEPLOYED" in text:
                vsc = True
            elif "VIRTUAL SAFETY CAR ENDING" in text:
                vsc = False
            elif "SAFETY CAR DEPLOYED" in text and "VIRTUAL" not in text:
                sc = True
            else:
                continue
        else:
            continue
        if red:
            code = RED
        elif sc:
            code = SAFETY_CAR
        elif vsc:
            code = VSC
        elif yellow_sectors:
            code = YELLOW
        else:
            code = GREEN
        timeline.append(_StatusChange(at, code))
    return timeline


def status_in_window(timeline: list[_StatusChange], start: datetime, end: datetime) -> str:
    """Most severe status active at any time in [start, end].

    The status in effect at `start` is the one set by the last change at or
    before `start`; every change in (start, end] is also active in the window.
    """
    current = GREEN
    worst = None
    for change in timeline:
        if change.at <= start:
            current = change.code
        elif change.at <= end:
            if worst is None or SEVERITY[change.code] > SEVERITY[worst]:
                worst = change.code
        else:
            break
    if worst is None or SEVERITY[current] > SEVERITY[worst]:
        worst = current
    return worst


# ------------------------------------------------------------------ drivers


def build_drivers(drivers: list[Mapping[str, Any]]) -> tuple[dict[int, DriverRecord], list[DriverRecord]]:
    """OpenF1 drivers rows -> ({driver_number: record}, records in input order)."""
    _require(drivers, DRIVER_FIELDS, "drivers")
    by_number: dict[int, DriverRecord] = {}
    for row in drivers:
        number = _int(row["driver_number"], "drivers.driver_number")
        code = _opt_str(row["name_acronym"])
        if code is None:
            raise ValueError(f"driver_number {number} has no name_acronym")
        record = DriverRecord(
            code=code,
            full_name=_opt_str(row["full_name"]),
            team=_opt_str(row["team_name"]),
            team_color=team_color(row["team_colour"]),
            grid_position=None,
        )
        previous = by_number.get(number)
        if previous is not None and previous != record:
            raise ValueError(f"conflicting drivers rows for driver_number {number}")
        by_number[number] = record
    codes = [r.code for r in by_number.values()]
    dupes = sorted({c for c in codes if codes.count(c) > 1})
    if dupes:
        raise ValueError(f"name_acronym shared by several driver numbers: {', '.join(dupes)}")
    return by_number, list(by_number.values())


# -------------------------------------------------------------------- laps


def normalize_openf1(
    session: Mapping[str, Any],
    laps: list[Mapping[str, Any]],
    stints: list[Mapping[str, Any]],
    pits: list[Mapping[str, Any]],
    drivers: list[Mapping[str, Any]],
    race_control: list[Mapping[str, Any]],
) -> tuple[pd.DataFrame, list[DriverRecord]]:
    """OpenF1 payloads of one race session -> (laps in LAP_COLUMNS, driver records).

    Raises KeyError naming missing OpenF1 fields, ValueError for malformed
    values, laps whose driver_number has no drivers row, or duplicate laps.
    Rows are sorted by driver code then lap.
    """
    if not isinstance(session, Mapping):
        raise TypeError("OpenF1 session must be an object")
    if "date_start" not in session:
        raise KeyError("OpenF1 session missing field(s): date_start")
    session_start = parse_time(session["date_start"], "session.date_start")
    _require(laps, LAP_FIELDS, "laps")
    _require(stints, STINT_FIELDS, "stints")
    _require(pits, PIT_FIELDS, "pit")
    by_number, records = build_drivers(drivers)
    timeline = track_status_timeline(race_control)

    unknown = sorted({_int(r["driver_number"], "laps.driver_number") for r in laps} - by_number.keys())
    if unknown:
        raise ValueError(
            f"laps reference driver_number(s) with no drivers row: {', '.join(map(str, unknown))}"
        )

    stints_by_driver: dict[int, list[tuple[int | None, int | None, int, Any, int | None]]] = {}
    for s in stints:
        number = _int(s["driver_number"], "stints.driver_number")
        stints_by_driver.setdefault(number, []).append(
            (
                _opt_int(s["lap_start"], "stints.lap_start"),
                _opt_int(s["lap_end"], "stints.lap_end"),
                _int(s["stint_number"], "stints.stint_number"),
                s["compound"],
                _opt_int(s["tyre_age_at_start"], "stints.tyre_age_at_start"),
            )
        )
    pit_laps = {
        (_int(p["driver_number"], "pit.driver_number"), _int(p["lap_number"], "pit.lap_number"))
        for p in pits
        if p["lap_number"] is not None
    }

    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for r in laps:
        number = _int(r["driver_number"], "laps.driver_number")
        if r["lap_number"] is None:
            raise ValueError(f"lap without lap_number for driver_number {number}")
        lap = _int(r["lap_number"], "laps.lap_number")
        if lap < 1:
            raise ValueError(f"lap_number {lap} < 1 for driver_number {number}")
        if (number, lap) in seen:
            raise ValueError(f"duplicate lap {lap} for driver_number {number}")
        seen.add((number, lap))
        driver = by_number[number]

        duration = _opt_float(r["lap_duration"], "laps.lap_duration")
        start = _opt_time(r["date_start"], "laps.date_start")
        if duration is not None and duration < 0:
            raise ValueError(f"negative lap_duration {duration} for driver_number {number} lap {lap}")
        if duration is None or start is None:
            session_time = None
            status = None
        else:
            session_time = (start - session_start).total_seconds() + duration
            status = status_in_window(timeline, start, start + timedelta(seconds=duration))

        stint = compound = tyre_life = None
        for lap_start, lap_end, number_, comp, age in stints_by_driver.get(number, []):
            if lap_start is None or lap < lap_start or (lap_end is not None and lap > lap_end):
                continue
            stint = number_
            compound = normalize_compound(comp)
            tyre_life = None if age is None else age + (lap - lap_start) + 1
            break

        pit_in = (number, lap) in pit_laps
        pit_out = bool(r["is_pit_out_lap"]) if r["is_pit_out_lap"] is not None else False
        rows.append(
            {
                "driver": driver.code,
                "team": driver.team,
                "lap": lap,
                "lap_time_s": duration,
                "session_time_s": session_time,
                "stint": stint,
                "compound": compound,
                "tyre_life": tyre_life,
                "pit_in": pit_in,
                "pit_out": pit_out,
                "track_status": status,
                "is_accurate": duration is not None and lap > 1 and not pit_in and not pit_out,
            }
        )

    out = pd.DataFrame(rows, columns=list(LAP_COLUMNS))
    out = out.astype(
        {
            "driver": "object",
            "team": "object",
            "lap": "int64",
            "lap_time_s": "float64",
            "session_time_s": "float64",
            "stint": "Int64",
            "compound": "object",
            "tyre_life": "Int64",
            "pit_in": "bool",
            "pit_out": "bool",
            "track_status": "object",
            "is_accurate": "bool",
        }
    )
    for col in ("team", "compound", "track_status"):
        out[col] = out[col].astype("object").where(out[col].notna(), None)
    out = out.sort_values(["driver", "lap"], kind="stable").reset_index(drop=True)
    return out.loc[:, list(LAP_COLUMNS)], records


# ================================================================ HTTP client

Opener = Callable[..., Any]  # (request, timeout=...) -> response with .status/.read()


class OpenF1Client:
    """Throttled, retrying, caching GET client for the fixed OpenF1 base URL."""

    def __init__(
        self,
        cache_root: Path,
        *,
        opener: Opener | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        timeout: float = TIMEOUT_S,
        retry_waits: Sequence[float] = RETRY_WAITS_S,
        max_per_second: int = MAX_REQUESTS_PER_SECOND,
    ) -> None:
        self.cache_root = Path(cache_root)
        self._opener = opener or urllib.request.urlopen
        self._sleep = sleep
        self._clock = clock
        self._timeout = timeout
        self._retry_waits = tuple(retry_waits)
        self._min_interval = 1.0 / max_per_second
        self._last_request: float | None = None
        self.requests = 0  # number of HTTP requests sent (for tests)

    # -- public ---------------------------------------------------------------

    def year_list(self, endpoint: str, year: int) -> list[dict[str, Any]]:
        """Year-level list; ``sessions`` returns Race sessions only."""
        if endpoint not in YEAR_ENDPOINTS:
            raise ValueError(f"endpoint {endpoint!r} is not filtered by year")
        year = _int(year, "year")
        filters, cache_name = YEAR_QUERIES[endpoint]
        return self._get(endpoint, {"year": year, **filters}, self.cache_root / str(year) / cache_name)

    def session_list(self, endpoint: str, session_key: int) -> list[dict[str, Any]]:
        if endpoint not in SESSION_ENDPOINTS:
            raise ValueError(f"endpoint {endpoint!r} is not a session endpoint")
        key = _int(session_key, "session_key")
        if key <= 0:
            raise ValueError(f"session_key must be positive, got {key}")
        return self._get(endpoint, {"session_key": key}, self.cache_root / str(key) / f"{endpoint}.json")

    # -- internals ------------------------------------------------------------

    def _get(self, endpoint: str, params: Mapping[str, Any], cache_path: Path) -> list[dict[str, Any]]:
        if cache_path.exists():
            with cache_path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, list):
                raise OpenF1Error(f"cached {cache_path} is not a JSON list")
            return data
        data = self._fetch(endpoint, params)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_name(f".{cache_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, cache_path)
        finally:
            tmp.unlink(missing_ok=True)
        return data

    def _url(self, endpoint: str, params: Mapping[str, Any]) -> str:
        if endpoint not in ENDPOINTS:
            raise ValueError(f"endpoint {endpoint!r} is not allowed")
        return f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(dict(params))}"

    def _throttle(self) -> None:
        now = self._clock()
        if self._last_request is not None:
            wait = self._last_request + self._min_interval - now
            if wait > 0:
                self._sleep(wait)
                now = self._clock()
        self._last_request = now

    def _fetch(self, endpoint: str, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        url = self._url(endpoint, params)
        request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "augur-ingest"})
        attempt = 0
        while True:
            self._throttle()
            self.requests += 1
            status, body = self._send(request)
            if status == 200:
                break
            if status == 404 and _is_no_results(body):
                return []
            retryable = status == 429 or 500 <= status <= 599
            if not retryable or attempt >= len(self._retry_waits):
                tried = f" after {attempt} retries" if retryable else ""
                raise OpenF1Error(f"OpenF1 {endpoint} request failed: HTTP {status}{tried}")
            self._sleep(self._retry_waits[attempt])
            attempt += 1
        try:
            data = json.loads(body)
        except ValueError as exc:
            raise OpenF1Error(f"OpenF1 {endpoint} returned invalid JSON") from exc
        if not isinstance(data, list):
            raise OpenF1Error(f"OpenF1 {endpoint} returned {type(data).__name__}, expected a list")
        return data

    def _send(self, request: urllib.request.Request) -> tuple[int, bytes]:
        try:
            with self._opener(request, timeout=self._timeout) as resp:
                return int(getattr(resp, "status", 200)), resp.read()
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read() if exc.fp is not None else b""
            finally:
                exc.close()
            return int(exc.code), body


def _is_no_results(body: bytes) -> bool:
    """True for OpenF1's empty-result 404 body ``{"detail": "No results found."}``."""
    try:
        data = json.loads(body)
    except ValueError:
        return False
    return isinstance(data, dict) and data.get("detail") == NO_RESULTS_DETAIL


# ============================================================ race resolution


@dataclass(frozen=True)
class RacePayload:
    """Everything fetched from OpenF1 for one round."""

    session: dict[str, Any]
    meeting_name: str
    laps: list[dict[str, Any]]
    stints: list[dict[str, Any]]
    pits: list[dict[str, Any]]
    drivers: list[dict[str, Any]]
    race_control: list[dict[str, Any]]


def resolve_race_session(sessions: list[Mapping[str, Any]], round_: int) -> Mapping[str, Any]:
    """Round R = R-th non-cancelled Race session ordered by date_start."""
    _require(sessions, SESSION_FIELDS, "sessions")
    races = [s for s in sessions if s.get("session_name", "Race") == "Race" and s["is_cancelled"] is not True]
    races.sort(key=lambda s: parse_time(s["date_start"], "sessions.date_start"))
    if not 1 <= round_ <= len(races):
        raise LookupError(f"no race session for round {round_}")
    return races[round_ - 1]


def meeting_name(meetings: list[Mapping[str, Any]], meeting_key: Any) -> str:
    _require(meetings, MEETING_FIELDS, "meetings")
    for m in meetings:
        if m["meeting_key"] == meeting_key:
            name = _opt_str(m["meeting_name"])
            if name is None:
                break
            return name
    raise LookupError(f"no meeting name for meeting_key {meeting_key}")


def load_openf1_race(
    year: int, round_: int, data_dir: Path, *, client: OpenF1Client | None = None
) -> RacePayload:
    """Fetch (or read from cache) every payload of the race session of a round."""
    client = client or OpenF1Client(catalog.openf1_cache_dir(data_dir))
    session = dict(resolve_race_session(client.year_list("sessions", year), round_))
    name = meeting_name(client.year_list("meetings", year), session["meeting_key"])
    key = session["session_key"]
    payloads = {endpoint: client.session_list(endpoint, key) for endpoint in SESSION_ENDPOINTS}
    return RacePayload(
        session=session,
        meeting_name=name,
        laps=payloads["laps"],
        stints=payloads["stints"],
        pits=payloads["pit"],
        drivers=payloads["drivers"],
        race_control=payloads["race_control"],
    )
