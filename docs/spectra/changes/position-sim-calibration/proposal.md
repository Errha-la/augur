## Problem

AUGUR's headline output, finishing-position probability, scores worse than the trivial "current order holds" rule. `bench/lightgbm.json` (2026-11-20) reports a pooled podium skill of −15.9%. The forecasts are also badly overconfident: in `data/augur.sqlite`, 85–100% of the stored `p_podium` values at the benchmark checkpoints are below 0.02 or above 0.98 (measured 2026-11-22), and some favourites are implausible, for example HUL `p_win` 1.0 at Bahrain lap 14 and HUL `p_win` 0.83 from P7 at Abu Dhabi lap 13. The project cannot be shown as a portfolio piece while its headline number is negative.

## Root Cause

Measured on Bahrain 2024 at lap 14 with `lightgbm` (`augur.positions.driver_starts`, 2026-11-22):

1. **One-lap prediction projected to the flag.** `base_s` is the model's `predicted_next_lap_s`, a one-lap forecast (recent pace plus a delta). The simulator applies it to every remaining lap, so a transient delta becomes a race-long pace gap: TSU −2.04 s, NOR −1.76 s, PER −1.57 s, about 80 s over 43 laps for TSU.
2. **Unguarded compound median fallback.** The 8-clean-lap guard covers only a driver's own fit. The fallback `compound_median_slopes` takes the median over every stint fit with at least 4 laps; at lap 14 the HARD median was 0.408 s/lap, from short, fresh stints. Every HARD runner got that slope for 43 laps, about +386 s each.
3. **No race-long uncertainty.** The only randomness is independent lap noise (σ ≥ 0.2 s) and the pit-lap jitter. Independent noise averages out over many laps (about 0.2 × √43 ≈ 1.3 s), so small pace differences decide the order almost every run.

Smaller issues: a fresh tyre has the same pace whatever its compound; `strategy.simulate` draws independent noise per candidate, so its `win_probability` mostly measures noise; neither simulator has safety cars, although a safety car is when most cheap stops happen.

## Proposed Solution

- Base pace becomes the driver's recent pace (median of the last 3 clean laps). The model's delta applies to the next lap and decays geometrically over the following laps instead of lasting to the flag.
- A new guarded compound slope (used by the simulators only) counts only stint fits with at least 8 clean laps, shrinks the race median toward the circuit prior, and caps the result. `compound_median_slopes` stays unchanged because circuit priors and model features use it.
- Each simulated run draws a per-driver pace offset that lasts the whole run, so uncertainty grows with the laps remaining.
- Fresh tyres get a per-compound pace offset in both simulators.
- `strategy.simulate` uses common random numbers across candidates, and a new public `strategy.simulate_pit_laps()` simulates any list of pit laps (the `strategy-charts-api` change builds its pit-window curve on it).
- The position simulator draws safety-car and virtual-safety-car periods: these compress gaps (safety car only), slow laps, and make a stop cheaper, so drivers who still need a stop usually take it then.
- The simulator also reports each driver's full finishing-position distribution, stored with the existing per-lap predictions.
- The benchmark adds a log loss and a reliability table for `p_podium`. A new evaluation-only run on 2024 rounds 12 to 23 tunes the new constants without touching the two benchmark races.

## Non-Goals (optional)

Recorded in design.md.

## Success Criteria

- Pooled podium skill on the benchmark races is reported for `lightgbm` and `baseline` after the change, measured by `python -m augur.bench`. Target: above 0% for both. If the target is missed, the measured number is still reported and the gap is recorded as an open issue; no number is hidden or tuned on the benchmark races.
- The share of checkpoint `p_podium` values below 0.02 or above 0.98 drops from 85–100% per race (measured 2026-11-22) to at most 60% on each benchmark race.
- On Bahrain lap 14 no driver outside the top 6 has `p_win` above 0.5.
- All leakage tests still pass, and the new tests in tasks.md pass.

## Impact

- Affected specs: `position-prediction` (modified), `strategy-simulation` (modified), `model-benchmark` (modified).
- Affected code:
  - Modified: backend/src/augur/positions.py, backend/src/augur/strategy.py, backend/src/augur/models/degradation.py, backend/src/augur/config.py, backend/src/augur/scoring.py, backend/src/augur/bench.py, backend/src/augur/analyze.py, backend/src/augur/catalog.py, backend/src/augur/replay.py, bench/lightgbm.json, bench/baseline.json
  - New: backend/tests/test_positions_calibration.py, backend/tests/test_strategy_plans.py, backend/tests/test_bench_eval.py, bench/lightgbm-eval.json, bench/baseline-eval.json
  - Removed: none
- Data: re-analysis of both benchmark races and 2024 rounds 12 to 23 (rounds 12 to 23 must be ingested first; needs network). Event `next` texts that quote strategy numbers change, so some cached LLM commentary may no longer pass its grounding check.
- API: no route or response change in this change; `/positions` field additions belong to `strategy-charts-api`.
