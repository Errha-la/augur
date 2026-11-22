"""Summaries for task 5.1 from bench JSON files and stored position predictions."""
import json
import sys
from pathlib import Path

from augur.replay import ReplayStore
from augur.scoring import checkpoints

data_dir, bench_dir = sys.argv[1], Path(sys.argv[2])
for name in ("lightgbm", "baseline", "lightgbm-eval", "baseline-eval"):
    r = json.loads((bench_dir / f"{name}.json").read_text())
    print(f"## {name}: skill {r['position_skill_pct']}% brier {r['brier_model']} vs {r['brier_baseline']}, "
          f"log loss {r['log_loss_model']} vs {r['log_loss_baseline']}")
    print("   reliability:", "; ".join(
        f"[{b['bin_low']},{b['bin_high']}) n={b['count']} f={b['mean_forecast']} o={b['observed_rate']}"
        for b in r["reliability"]))
    for p in r["per_race"]:
        print(f"   {p['race_id']}: skill {p['position_skill_pct']}% log loss {p['log_loss_model']} vs {p['log_loss_baseline']}")

store = ReplayStore(data_dir)
for model in ("lightgbm", "baseline"):
    for race_id in ("2024-01-bahrain-grand-prix", "2024-24-abu-dhabi-grand-prix"):
        total = int(store.get_race(race_id)["total_laps"])
        cps = set(checkpoints(total))
        vals = [r["p_podium"] for r in store.positions_until(race_id, model, total) if r["lap"] in cps]
        extreme = sum(v < 0.02 or v > 0.98 for v in vals)
        print(f"extreme p_podium {model} {race_id}: {extreme}/{len(vals)} = {100 * extreme / len(vals):.0f}%")
    rows = store.positions_until("2024-01-bahrain-grand-prix", model, 14, only_lap=True)
    top = sorted(rows, key=lambda r: -r["p_win"])[:5]
    print(f"Bahrain lap 14 {model} p_win leaders:", ", ".join(f"{r['code']} {r['p_win']:.3f}" for r in top))

from augur.state import positions_by_lap  # noqa: E402

laps = store.laps_until("2024-01-bahrain-grand-prix", 14)
order = positions_by_lap(laps, store.list_drivers("2024-01-bahrain-grand-prix"),
                         {"race_id": "2024-01-bahrain-grand-prix", "total_laps": 57}, [14])[14]
for model in ("lightgbm", "baseline"):
    rows = store.positions_until("2024-01-bahrain-grand-prix", model, 14, only_lap=True)
    outside = [(r["code"], order.get(r["code"]), r["p_win"]) for r in rows if order.get(r["code"], 99) > 6 and r["p_win"] > 0.5]
    print(f"Bahrain lap 14 {model}: drivers outside top 6 with p_win > 0.5: {outside}")
