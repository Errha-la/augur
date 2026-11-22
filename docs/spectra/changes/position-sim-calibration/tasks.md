## 1. Strategy simulator

- [x] 1.1 Add `strategy.simulate_pit_laps()` and rebuild `strategy.simulate()` on it with common random numbers, per "Common random numbers and pit-lap plans in strategy" and the "Pit-lap plan simulation" and "Reproducible Monte Carlo results" requirements: one shared noise draw per run for every plan, plans in input order, `ValueError` for a pit lap outside [lap+1, total_laps − 2], unchanged `simulate()` signature and response. Verify with new tests in `backend/tests/test_strategy_plans.py` (same numbers as the comparison, out-of-range pit lap, shared draws give `win_probability` 1.0 for a dominated plan, same seed twice) plus the existing `backend/tests/test_strategy.py` and `backend/tests/test_strategy_api.py`. Merge to `main` when green, per "Wave 1 backend track BE-1".
- [x] 1.2 Add the compound pace offset to the strategy model ("Compound pace offset on fresh tyres", "Candidate pit strategies" requirement): `COMPOUND_PACE_OFFSET_S` in `augur.config`, applied to the current and the post-stop compound. Verify with a test in `backend/tests/test_strategy_plans.py` for the "Harder compound costs time" scenario. [after: 1.1]

## 2. Position simulator

- [x] 2.1 Add the guarded compound slope to `augur.models.degradation` ("Guarded compound slope for the simulators"): fits with at least 8 clean laps, shrinkage toward the circuit prior or default with `DEG_SHRINK_STINTS`, clamp to [0, `DEG_CAP_S_PER_LAP`]; use it in `augur.positions` and `augur.strategy` in place of the race median, and cap a driver's own trusted slope. `compound_median_slopes` stays as is. Verify with tests in `backend/tests/test_positions_calibration.py` for the "Guarded compound slope ignores short stints" example (0.038 s/lap) and the "Short or negative stint fit" scenario, and confirm `backend/tests/test_priors.py` and `backend/tests/test_features.py` pass unchanged. [after: 1.2]
- [x] 2.2 Replace the base pace in "Simulate the remaining race for every driver" with recent pace plus a decaying model delta ("Recent pace as base, model delta decays"), with `MODEL_DELTA_DECAY` 0.5 in `augur.config` and the existing fallbacks when there is no prediction. Verify with the "Model delta fades" scenario test (88.0, 89.0, 89.5 s) in `backend/tests/test_positions_calibration.py`, plus `backend/tests/test_positions.py` and `backend/tests/test_no_future_leak.py`. [after: 2.1]
- [x] 2.3 Add the per-run pace offset ("Per-run pace offset", `PACE_OFFSET_SD_S` 0.15) and the compound pace offset after a simulated stop to `simulate_finish`. Verify with the "Uncertainty grows with laps remaining" scenario test and the "Dominant leader" and "Deterministic per lap" tests in `backend/tests/test_positions.py`; update any existing expected number that changes and note it under this task. [after: 2.2]
- [x] 2.4 Report and store the "Finishing-position distribution" ("Store the finishing-position distribution"): `position_distribution` from `summarize`, a JSON column in `position_predictions` added by `ALTER TABLE` on old databases, written by `python -m augur.analyze`, returned by `ReplayStore.positions_until` only with `include_distribution=True`. Verify with the "Distribution sums" and "Old database" scenario tests in `backend/tests/test_positions_calibration.py` and `backend/tests/test_analyze_positions.py`, and confirm `backend/tests/test_positions_api.py` shape tests pass unchanged. Merge to `main` when green. [after: 2.3]

## 3. Benchmark, evaluation races, tuning

- [x] 3.1 Add the "Podium calibration report" ("Podium calibration in the benchmark") to `augur.scoring` and to pooled and per-race output of "Score a model on the benchmark races". Verify with the "Calibration arithmetic" example test (log loss 0.3993) in `backend/tests/test_scoring.py` and the existing "Summary line" and "Same model twice" tests in `backend/tests/test_bench.py`.
- [x] 3.2 Add `--eval` to `python -m augur.bench` for the "Evaluation races" requirement (2024 rounds 12 to 23, `bench/<name>-eval.json`, same refusals, benchmark file untouched). Verify with the "Evaluation race missing" and "Benchmark file untouched" scenario tests in `backend/tests/test_bench_eval.py` on synthetic data. [after: 3.1]
- [x] 3.3 Ingest 2024 rounds 12 to 23 for evaluation with `backend/.venv/bin/python -m augur.ingest --year 2024 --rounds $(seq 12 23)` (needs network). Record elapsed time and per-race laps here, and list any round that failed. Verify with `GET /api/races` listing all twelve evaluation races.
- [x] 3.4 Add `python -m augur.tune_sim` ("Evaluation races 2024 rounds 12 to 23 for tuning") and run it for `lightgbm`; set `PACE_OFFSET_SD_S` and `MODEL_DELTA_DECAY` in `augur.config` to the combination with the lowest pooled Brier (log loss breaks ties) and paste the 15-line table here. Also record per-compound fuel-corrected intercept differences on the evaluation races to check `COMPOUND_PACE_OFFSET_S`. Verify with the "Tuning grid output" scenario test (15 lines) in `backend/tests/test_bench_eval.py` on synthetic data. [after: 2.4, 3.2, 3.3]

## 4. Neutralised periods

- [x] 4.1 Add "Neutralised periods" ("Safety car and virtual safety car periods") to `simulate_finish`, with the constants in `augur.config` and the safety-car stop rule of "Expected pit plan". Verify with the "Safety car compresses the field", "No safety cars", and "Stop taken under a safety car" scenario tests in `backend/tests/test_positions_calibration.py`, plus `backend/tests/test_no_future_leak.py`. Compare the simulated period rate with the number of safety cars and virtual safety cars in the race-control-derived `track_status` of the evaluation races and record both here. [after: 3.4]

## 5. Measured results

- [x] 5.1 Re-analyze both benchmark races and the evaluation races for `lightgbm` and `baseline`, run `python -m augur.bench --model lightgbm`, `--model baseline`, and both with `--eval`, and record here: pooled and per-race podium skill, log loss, reliability bins, the share of checkpoint `p_podium` values outside [0.02, 0.98] per benchmark race (before: 85–100%), the Bahrain lap 14 `p_win` leaders, and the number of cached commentary texts in `data/augur.sqlite` that no longer pass `augur.narration.grounding` after re-analysis. Check the proposal's success criteria against these numbers and write README notes for `portfolio-release` under this task. Verify by committing `bench/lightgbm.json`, `bench/baseline.json`, `bench/lightgbm-eval.json`, `bench/baseline-eval.json` produced by these commands and the full backend suite passing. [after: 4.1]


## Implementation notes and measured results (2026-11-22)

Scripts used for the checks below are in `measurements/` of this change (run from `backend/` with `PYTHONPATH=src`).

### 1.1 Shared draws

- With common random numbers and purely additive lap noise, the difference between two plans is the same in every run, so the plan with the lowest `mean_s` always gets `win_probability` 1.0 (others 0.0). This follows the design ("measures the plans' difference"), but event `next` texts now read "fastest option in 100% of simulations". **Open decision:** keep, or add plan-dependent randomness (for example per-run degradation uncertainty) in a later change.
- Tasks 1.1 and 2.4 were not merged to `main` by this session (merging is left to the user); they are on branch `worktree-position-sim-calibration` (checkpoint commit 03bb5c0).

### 2.1 Guarded slope in strategy

- `strategy.simulate()` has no circuit prior (its signature is fixed), so its guarded slope shrinks toward `DEG_FALLBACK_S_PER_LAP`; the position simulator uses the circuit prior. `strategy.py` keeps a driver's own stint fit (from 4 clean laps), as before, because its base pace is that fit's intercept.

### 2.3 / 4.1 Changed existing tests

- `test_positions.py::test_slightly_faster_car_stays_behind` and `::test_much_faster_car_passes` now set `PACE_OFFSET_SD_S`, `SC_PROB_PER_LAP`, and `VSC_PROB_PER_LAP` to 0: they assert every run, and the per-run offset (22% of runs swapped at 0.15 s) and neutralised laps (no dirty air) are not what they test. `test_probability_sums` now also expects `position_distribution`. `test_bench.py` result keys gained the three calibration keys.

### 3.3 Ingest of 2024 rounds 12 to 23

- First run 752 s: rounds 12 to 22 ingested; round 23 failed with "The read operation timed out". Retry of round 23 alone: 9 s, success.
- Laps (20 drivers each): British 52, Hungarian 70, Belgian 44, Dutch 72, Italian 53, Azerbaijan 51, Singapore 62, United States 56, Mexico City 71, São Paulo 69, Las Vegas 50, Qatar 57. `GET /api/races` lists all twelve.
- No 2023 races at these locations were ingested, so circuit priors exist on an evaluation race only where the 2023 race was already in `data/`.

### 3.4 Tuning (`python -m augur.tune_sim --model lightgbm`, 1000 runs, 32 s)

```
offset_sd=0.05 decay=0.3 brier=0.0879 log_loss=0.4515
offset_sd=0.05 decay=0.5 brier=0.0878 log_loss=0.4494
offset_sd=0.05 decay=0.7 brier=0.0878 log_loss=0.4468
offset_sd=0.10 decay=0.3 brier=0.0848 log_loss=0.4175
offset_sd=0.10 decay=0.5 brier=0.0847 log_loss=0.417
offset_sd=0.10 decay=0.7 brier=0.0844 log_loss=0.4132
offset_sd=0.15 decay=0.3 brier=0.0819 log_loss=0.3804
offset_sd=0.15 decay=0.5 brier=0.0817 log_loss=0.3801
offset_sd=0.15 decay=0.7 brier=0.0813 log_loss=0.3753
offset_sd=0.20 decay=0.3 brier=0.0791 log_loss=0.3416
offset_sd=0.20 decay=0.5 brier=0.0788 log_loss=0.3397
offset_sd=0.20 decay=0.7 brier=0.0783 log_loss=0.3373
offset_sd=0.30 decay=0.3 brier=0.074 log_loss=0.2903
offset_sd=0.30 decay=0.5 brier=0.0738 log_loss=0.2893
offset_sd=0.30 decay=0.7 brier=0.0733 log_loss=0.2843
```

- Chosen: `PACE_OFFSET_SD_S` 0.30, `MODEL_DELTA_DECAY` 0.7. Both are at the grid edge and Brier still falls as the offset grows, so the best value is probably outside the grid. **Open issue:** widen the grid in a later change.
- Compound intercepts (`measurements/intercepts.py`; same driver and race, stints with at least 8 clean laps, median of X − MEDIUM): SOFT +0.775 s (n=18), HARD +0.022 s (n=150). The estimates SOFT −0.6 and HARD +0.4 are **not confirmed**; they stay unchanged because the design tunes only two constants. **Open issue.**

### 4.1 Neutralised periods vs race control (`measurements/sc_rates.py`)

| Race | Laps | Actual SC | Actual VSC | Simulated SC | Simulated VSC |
|---|---|---|---|---|---|
| British | 52 | 0 | 0 | 0.29 | 0.22 |
| Hungarian | 70 | 0 | 0 | 0.35 | 0.27 |
| Belgian | 44 | 0 | 0 | 0.25 | 0.19 |
| Dutch | 72 | 0 | 0 | 0.36 | 0.27 |
| Italian | 53 | 0 | 0 | 0.29 | 0.22 |
| Azerbaijan | 51 | 0 | 1 | 0.28 | 0.22 |
| Singapore | 62 | 0 | 0 | 0.32 | 0.25 |
| United States | 56 | 1 | 0 | 0.30 | 0.23 |
| Mexico City | 71 | 1 | 0 | 0.35 | 0.27 |
| São Paulo | 69 | 2 | 1 | 0.35 | 0.26 |
| Las Vegas | 50 | 0 | 0 | 0.28 | 0.21 |
| Qatar | 57 | 2 | 1 | 0.31 | 0.23 |
| **Total** | | **6** | **3** | **3.7** | **2.8** |

- Simulated safety cars are below the actual count: a run holds at most one period, so the first-draw rule gives about 0.31 safety cars per 57 laps, not the design's 0.45 estimate.

### 5.1 Measured results (`measurements/run51.sh`, 727 s; baseline model trained first with `python -m augur.train --model baseline --train 2024:2-11 --test 2024:1,24`)

| | Podium skill | Brier model / baseline | Log loss model / baseline |
|---|---|---|---|
| lightgbm, benchmark (before: −15.9%) | **49.0%** | 0.0255 / 0.05 | 0.0843 / 0.3463 |
| baseline, benchmark (before: 61.7%) | **48.7%** | 0.0256 / 0.05 | 0.086 / 0.3463 |
| lightgbm, evaluation races | 4.3% | 0.0744 / 0.0778 | 0.275 / 0.5382 |
| baseline, evaluation races | 2.7% | 0.0757 / 0.0778 | 0.2818 / 0.5382 |

- Per race, lightgbm: Bahrain −2.8% (log loss 0.1027 vs 0.2312), Abu Dhabi 74.9% (0.0659 vs 0.4615). Baseline: Bahrain −9.1%, Abu Dhabi 77.6%.
- Per evaluation race, lightgbm: British 40.4%, Hungarian −432.0%, Belgian 65.0%, Dutch −12.2%, Italian −19.3%, Azerbaijan 9.9%, Singapore −109.6%, United States 40.7%, Mexico City −32.0%, São Paulo −25.2%, Las Vegas 33.3%, Qatar 41.8%.
- Reliability, lightgbm benchmark (count, mean forecast, observed): [0,0.2) 97, 0.0137, 0.0; [0.2,0.4) 5, 0.2898, 0.4; [0.4,0.6) 2, 0.4365, 0.5; [0.6,0.8) 3, 0.6527, 1.0; [0.8,1.0] 13, 0.953, 0.9231. Evaluation races: [0,0.2) 576, 0.0119, 0.0365; [0.2,0.4) 28, 0.3009, 0.3929; [0.4,0.6) 25, 0.4821, 0.48; [0.6,0.8) 18, 0.6942, 0.5; [0.8,1.0] 73, 0.934, 0.7534 (high forecasts are still overconfident).
- Checkpoint `p_podium` outside [0.02, 0.98]: Bahrain 72% (43/60), Abu Dhabi 73% (44/60), both models (before: 85–100%).
- Bahrain lap 14 `p_win` leaders, lightgbm: VER 0.979, SAI 0.011, LEC 0.010 (before: HUL 1.0). No driver outside the top 6 has `p_win` above 0.5 (both models).
- Cached commentary (lightgbm, openai_compat glm, en): 91 of 116 still pass grounding, **25 no longer pass** after re-analysis. Regenerating them is a separate `python -m augur.narrate` run.
- Full backend suite: 439 passed, 1 skipped (was 403 + 1 skipped).

Success criteria:

- Pooled podium skill above 0% for both models: **met** (49.0%, 48.7%).
- Extreme-forecast share at most 60% per benchmark race: **missed** (72%, 73%). Many of the 20 drivers are far from the podium, so near-0 forecasts are partly correct; the tuning trend suggests a larger pace offset would lower the share. **Open issue.**
- Bahrain lap 14, no driver outside the top 6 with `p_win` above 0.5: **met**.
- Leakage tests and new tests pass: **met**.
- lightgbm beats the baseline model by only 0.3 points on the benchmark: with the delta decaying, the simulator mostly follows recent pace.

README notes for `portfolio-release`:

- Headline: "Finishing-position forecasts beat 'current order holds' by 49.0% (podium Brier skill, Bahrain and Abu Dhabi 2024, lightgbm); 4.3% on twelve held-out 2024 races (rounds 12 to 23)."
- Method: Monte Carlo of the remaining laps from recent pace, a fading lap-time-model delta, guarded tyre degradation, a per-run pace offset, and safety-car / VSC periods; constants tuned on rounds 12 to 23 only.
- Caveat: the per-race skill varies widely (Hungary −432%, Singapore −110%), and forecasts above 0.8 are overconfident on the evaluation races.
