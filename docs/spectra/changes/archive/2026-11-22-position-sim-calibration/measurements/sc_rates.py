"""Actual SC / VSC periods (from per-lap track_status) vs simulated rates on the evaluation races.

track_status is a string of status digits per lap (OpenF1 race control): '4' safety car,
'6' or '7' virtual safety car. A period is a run of consecutive laps carrying the code.
"""
import sys

import numpy as np

from augur.bench import EVAL_ROUNDS, resolve_rounds
from augur.positions import SAFETY_CAR, VIRTUAL_SAFETY_CAR, sample_periods
from augur.replay import ReplayStore

data_dir = sys.argv[1]
store = ReplayStore(data_dir)
tot = {"sc": 0, "vsc": 0, "sim_sc": 0.0, "sim_vsc": 0.0}
for race_id in resolve_rounds(data_dir, EVAL_ROUNDS):
    total = int(store.get_race(race_id)["total_laps"])
    laps = store.laps_until(race_id, total)
    by_lap = laps.groupby("lap")["track_status"].apply(lambda s: "".join(str(x) for x in s.dropna()))
    counts = {}
    for name, codes in (("sc", "4"), ("vsc", "67")):
        flags = [any(c in by_lap.get(n, "") for c in codes) for n in range(1, total + 1)]
        counts[name] = sum(1 for i, f in enumerate(flags) if f and (i == 0 or not flags[i - 1]))
    _, kind = sample_periods(0, total, 20000, np.random.default_rng(0))
    sim_sc, sim_vsc = (kind == SAFETY_CAR).mean(), (kind == VIRTUAL_SAFETY_CAR).mean()
    tot["sc"] += counts["sc"]; tot["vsc"] += counts["vsc"]; tot["sim_sc"] += sim_sc; tot["sim_vsc"] += sim_vsc
    print(f"{race_id}: laps {total}, actual SC {counts['sc']} VSC {counts['vsc']}, simulated SC {sim_sc:.2f} VSC {sim_vsc:.2f}")
print(f"total over 12 races: actual SC {tot['sc']} VSC {tot['vsc']}, simulated SC {tot['sim_sc']:.1f} VSC {tot['sim_vsc']:.1f}")
