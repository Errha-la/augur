"""Per-compound fuel-corrected stint intercept differences vs MEDIUM on the evaluation races.

For each driver and race with a MEDIUM stint and another dry-compound stint (each with at
least 8 clean laps), take intercept(X) - intercept(MEDIUM); report the median per X.
"""
import sys
from statistics import median

from augur.bench import EVAL_ROUNDS, resolve_rounds
from augur.models.degradation import _clean_stints, fit_stint
from augur.replay import ReplayStore

data_dir = sys.argv[1]
store = ReplayStore(data_dir)
diffs = {"SOFT": [], "HARD": []}
for race_id in resolve_rounds(data_dir, EVAL_ROUNDS):
    total = int(store.get_race(race_id)["total_laps"])
    clean = _clean_stints(store.laps_until(race_id, total), total)
    for driver, g in clean.groupby("driver"):
        by_compound = {}
        for _, s in g.groupby("stint"):
            comps = s["compound"].dropna().unique()
            if len(comps) != 1 or len(s) < 8:
                continue
            fit = fit_stint(s["tyre_life"], s["fc_time"])
            if fit is not None:
                by_compound.setdefault(str(comps[0]), []).append(fit.intercept)
        if "MEDIUM" not in by_compound:
            continue
        med = median(by_compound["MEDIUM"])
        for c in ("SOFT", "HARD"):
            if c in by_compound:
                diffs[c].append(median(by_compound[c]) - med)
for c, v in diffs.items():
    print(f"{c} - MEDIUM: n={len(v)} median={median(v):+.3f} s" if v else f"{c}: n=0")
