"""Generate and cache LLM commentary for a race's analyzed events.

Usage:
    python -m augur.narrate --race <race_id> [--model lightgbm] [--narrator gemini|openai_compat|none] [--data-dir DIR]

The narrator defaults to $AUGUR_NARRATOR, else gemini.

Reads the events stored by ``augur.analyze`` with their outcome fields removed,
asks the narrator for commentary on each event without cached text, keeps only
grounded text, and stores it in the ``commentary`` table. Analysis, tests and
the benchmark never need this command or an API key.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from augur import catalog, config
from augur import settings as runtime_settings
from augur.events.outcomes import OUTCOME_FIELDS
from augur.narration import base
from augur.narration.base import MissingSettingError, is_connection_error
from augur.narration.cache import CommentaryKey, cached_texts, store_text
from augur.narration.grounding import check_grounding
from augur.narration.prompt import PROMPT_VERSION, check_lang
from augur.replay import ReplayStore

__all__ = ["MAX_CONNECTION_ERRORS", "PROMPT_VERSION", "main"]

# Stop after this many network errors in a row (no HTTP status): the server is unreachable.
MAX_CONNECTION_ERRORS = 3


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m augur.narrate", description="Generate and cache LLM commentary for race events."
    )
    p.add_argument("--race", required=True)
    p.add_argument("--model", default=config.DEFAULT_MODEL)
    p.add_argument(
        "--narrator",
        default=None,
        choices=base.narrator_names(),
        help=f"default: ${base.NARRATOR_ENV}, else {base.DEFAULT_NARRATOR}",
    )
    p.add_argument("--data-dir", type=Path, default=None, help="data root (default: repo data/)")
    return p


def _events_without_outcomes(store: ReplayStore, race_id: str, model: str, total_laps: int) -> list[dict]:
    # Outcome fields are dropped here so no narrator can ever see them.
    return [
        {k: v for k, v in e.items() if k not in OUTCOME_FIELDS}
        for e in store.events_until(race_id, model, total_laps)
    ]


def _error_label(exc: Exception | None) -> str:
    if exc is None:
        return "no text returned"
    code = getattr(exc, "code", None)
    return f"{type(exc).__name__} {code}" if code is not None else type(exc).__name__


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir: Path = args.data_dir if args.data_dir is not None else catalog.default_data_dir()
    store = ReplayStore(data_dir)
    race = store.get_race(args.race)
    if race is None:
        print(f"race not found: {args.race}", flush=True)
        return 1
    if not store.is_analyzed(args.race, args.model):
        print(f"race {args.race} is not analyzed for model {args.model}, run augur.analyze first", flush=True)
        return 1
    try:
        narrator = base.get_narrator(args.narrator or base.selected_narrator_name())
        # The dashboard's language setting (data/settings.json > $AUGUR_COMMENTARY_LANG), so
        # /events finds what this run stores.
        lang = check_lang(runtime_settings.current(data_dir).commentary_lang)
    except MissingSettingError as exc:
        print(f"{exc.setting} not set; nothing generated", flush=True)
        return 0
    except ValueError as exc:  # invalid AUGUR_NARRATOR, model name, server URL, or language
        print(str(exc), flush=True)
        return 1
    if narrator.name == base.NoneNarrator.name:
        print("narrator none; nothing generated", flush=True)
        return 0
    if hasattr(narrator, "lang"):
        narrator.lang = lang

    key = CommentaryKey(
        model=args.model,
        narrator=narrator.name,
        llm_model=getattr(narrator, "llm_model", narrator.name),
        lang=lang,
        prompt_version=PROMPT_VERSION,
    )
    events = _events_without_outcomes(store, args.race, args.model, int(race["total_laps"]))
    ok = rejected = failed = 0
    conn = catalog.connect(data_dir)
    try:
        cached = cached_texts(conn, (e["id"] for e in events), key)
        todo = [e for e in events if e["id"] not in cached]
        connection_errors = 0
        for i, event in enumerate(todo):
            text = narrator.narrate(event)
            if text is None:
                failed += 1
                error = getattr(narrator, "last_error", None)
                print(f"failed {event['id']}: {_error_label(error)}", flush=True)
                connection_errors = connection_errors + 1 if is_connection_error(error) else 0
                if connection_errors >= MAX_CONNECTION_ERRORS:
                    # An unreachable server would otherwise cost the full timeout per event.
                    skipped = len(todo) - i - 1
                    failed += skipped
                    print(
                        f"stopped after {connection_errors} connection errors in a row; {skipped} events not tried",
                        flush=True,
                    )
                    break
                continue
            connection_errors = 0
            grounding = check_grounding(text, event)
            if not grounding.accepted:
                rejected += 1
                print(f"rejected {event['id']}: {grounding.reason}", flush=True)
                continue
            # Commit per event so an interrupted run keeps what it already paid for.
            with conn:
                store_text(conn, event["id"], key, text)
            ok += 1
    finally:
        conn.close()
    print(
        f"narrated {args.race}: {ok} ok, {rejected} rejected, {failed} failed, {len(cached)} cached",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
