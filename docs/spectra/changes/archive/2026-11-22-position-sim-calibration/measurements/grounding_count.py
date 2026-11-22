"""Cached commentary texts vs the re-analyzed events: grounded, failing grounding, or orphaned."""
import sqlite3
import sys
from collections import Counter

from augur import catalog
from augur.narration.grounding import check_grounding
from augur.replay import ReplayStore

data_dir = sys.argv[1]
store = ReplayStore(data_dir)
conn = sqlite3.connect(catalog.db_path(data_dir))
rows = conn.execute("SELECT event_id, model, narrator, llm_model, lang, text FROM commentary").fetchall()
events = {}
for race in store.list_races():
    for model in {r[1] for r in rows}:
        for e in store.events_until(race["race_id"], model, int(race["total_laps"])):
            events[(e["id"], model)] = e
c = Counter()
for event_id, model, narrator, llm, lang, text in rows:
    e = events.get((event_id, model))
    if e is None:
        c[(model, narrator, llm, lang, "event gone")] += 1
    elif check_grounding(text, e).accepted:
        c[(model, narrator, llm, lang, "grounded")] += 1
    else:
        c[(model, narrator, llm, lang, "fails grounding")] += 1
for k, v in sorted(c.items()):
    print(*k, v)
