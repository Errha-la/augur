"""The ``commentary`` table: cached narrator output per event and settings.

A cache key is (event_id, model, narrator, llm_model, lang, prompt_version);
changing any of them makes ``augur.narrate`` generate new text.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class CommentaryKey:
    """Everything except the event that selects a cached text."""

    model: str
    narrator: str
    llm_model: str
    lang: str
    prompt_version: int

    def params(self) -> tuple:
        return (self.model, self.narrator, self.llm_model, self.lang, self.prompt_version)


_WHERE = "model = ? AND narrator = ? AND llm_model = ? AND lang = ? AND prompt_version = ?"


def cached_texts(conn: sqlite3.Connection, event_ids: Iterable[str], key: CommentaryKey) -> dict[str, str]:
    """{event_id: text} for the given events that have cached text under ``key``."""
    ids = list(event_ids)
    out: dict[str, str] = {}
    # Chunked to stay under SQLite's bound-parameter limit.
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        marks = ", ".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT event_id, text FROM commentary WHERE {_WHERE} AND event_id IN ({marks})",
            (*key.params(), *chunk),
        ).fetchall()
        out.update({r[0]: r[1] for r in rows})
    return out


def store_text(conn: sqlite3.Connection, event_id: str, key: CommentaryKey, text: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO commentary"
        " (event_id, model, narrator, llm_model, lang, prompt_version, text, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, *key.params(), text, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
