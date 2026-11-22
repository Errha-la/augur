## Context

`position-prediction` simulates the rest of the race for the whole field and is AUGUR's headline output. The benchmark (`python -m augur.bench`, 2026-11-20) gives `lightgbm` a pooled podium skill of −15.9% against "current order holds". A review on 2026-11-22 traced this to three causes in the simulator (see proposal.md, Root Cause): the one-lap model prediction is used as race-long pace, the compound-median degradation fallback is unguarded (HARD 0.408 s/lap at Bahrain lap 14), and the only randomness is independent lap noise, so forecasts are nearly always 0 or 1.

This is the BE-1 track of Stage 4 Wave 1 in `AGENTS.md`. It runs in parallel with `strategy-charts-api` (BE-2), `dashboard-canvas` (FE), and `release-setup` (OPS).

Measured inputs this design relies on (2026-11-22, Bahrain lap 14, `lightgbm`): model deltas from recent pace up to −2.04 s; HARD race median slope 0.408 s/lap; 85–100% of checkpoint `p_podium` values per benchmark race outside [0.02, 0.98].

## Goals / Non-Goals

**Goals:**

- Remove the three root causes and make forecast uncertainty grow with the laps remaining.
- Add safety-car and virtual-safety-car periods to the position simulator.
- Give `strategy.simulate` comparable candidates (common random numbers) and expose `strategy.simulate_pit_laps()` for the pit-window curve in `strategy-charts-api`.
- Store each driver's finishing-position distribution per lap for the heatmap in `strategy-chart-widgets`.
- Report calibration (log loss, reliability table) and add an evaluation run on 2024 rounds 12 to 23 used to tune the new constants, so the benchmark races stay untouched by tuning.

**Non-Goals:**

- No API route or response change. Serving `position_distribution` and new chart endpoints belongs to `strategy-charts-api`.
- No frontend change. The focus-panel note "Assumes a green race to the end" becomes inaccurate once safety cars are simulated; `strategy-chart-widgets` (Wave 2) updates it.
- No README edit; README notes are recorded in tasks.md for `portfolio-release`.
- No change to the `LapTimeModel` protocol, the features, `compound_median_slopes`, or training. Circuit priors and the `circuit_deg_prior_s` feature keep their current values, so no retraining is needed.
- No safety cars in `strategy.simulate`: it compares pit plans for a green race, as before.
- No overtaking model beyond the existing dirty-air penalty, and no data-driven safety-car rates per circuit (constants are estimates).
- Benchmark races and the headline podium-skill formula do not change.

## Decisions

### Recent pace as base, model delta decays

**Supersedes**: position-prediction / Full-field lap-by-lap simulation

The simulator still runs `runs` independent futures for laps N+1 to `total_laps`, vectorized as (runs, drivers), seeded with `seed + N`, from each driver's cumulative session time and laps completed at lap N; lapped drivers keep their deficit. What changes is the pace term. A simulated lap j for driver d on the current stint is

`recent_d + delta_d × DECAY^(j−N−1) + deg_d × (j − N) − fuel_gain × (j − N) + offset_{run,d} + noise`

where `recent_d` is d's recent pace (median of the last 3 clean laps, the same value `predictions_at` reports as `recent_pace_s`), `delta_d` is the lap-time model's predicted delta for lap N+1 (`predicted_next_lap_s − recent_pace_s`), and `MODEL_DELTA_DECAY` (initial estimate 0.5, tuned in "Evaluation races 2024 rounds 12 to 23 for tuning") shrinks the delta each lap. Without a model prediction, `recent_d` falls back as before (median of d's laps after lap 1, then the field median; at lap 1 every driver gets the median of all lap times so far) and `delta_d` is 0. Reason: the model is trained and scored as a next-lap forecast (MAE 0.305 s vs 0.380 s); using it for 43 laps turned a −2.04 s one-lap delta into an 80 s gap. Alternative: drop the model from the simulator entirely. Rejected because the next laps are where the model adds skill, and AUGUR's model swap must still change the forecast.

### Guarded compound slope for the simulators

**Supersedes**: position-prediction / Projected degradation uses only trusted stint fits

A new function in `augur.models.degradation` returns the per-compound slope the simulators use when a driver's own fit is not trusted, and the slope after a simulated stop:

1. Take stint fits up to lap N with at least `POSITION_DEG_MIN_FIT_LAPS` (8) clean laps and a single compound.
2. Shrink their median toward a prior: `(k × median + K × prior) / (k + K)`, where k is the number of such fits, `K = DEG_SHRINK_STINTS` (3, estimate) and `prior` is the circuit prior for that compound (`augur.priors.circuit_priors`), else the per-compound default (SOFT 0.085, MEDIUM 0.050, HARD 0.028 s/lap). With no qualifying fit the result is the prior.
3. Clamp to `[0, DEG_CAP_S_PER_LAP]` (0.20 s/lap, estimate; above the SOFT default with margin).

A driver's own slope is used only when its fit has at least 8 clean laps and a non-negative slope, as before, and is also capped at `DEG_CAP_S_PER_LAP`. `compound_median_slopes` stays unchanged, because circuit priors and the `circuit_deg_prior_s` model feature are built on it; changing it would require retraining. Alternative: raise the median's own minimum to 8 laps without shrinkage. Rejected because early in a race no stint has 8 laps, so the fallback would jump from the default to a single noisy fit.

### Per-run pace offset

Each run draws one offset per driver, `offset_{run,d} ~ Normal(0, PACE_OFFSET_SD_S)`, added to every simulated lap of that run (initial estimate 0.15 s/lap, tuned on the evaluation races). Lap noise stays as before (d's clean-lap residual standard deviation, minimum 0.2 s). Reason: independent lap noise averages out (about 1.3 s over 43 laps at σ = 0.2 s), while real uncertainty about a driver's pace lasts the whole race; with the offset the spread grows roughly linearly with the laps remaining. Alternative: inflate lap noise. Rejected because it still averages out and would distort the dirty-air interaction lap by lap.

### Compound pace offset on fresh tyres

Both simulators add `COMPOUND_PACE_OFFSET_S[compound]` to the pace on a compound: SOFT −0.6, MEDIUM 0.0, HARD +0.4 s/lap (estimates; confirm by comparing fuel-corrected stint intercepts per compound on the evaluation races, recorded in tasks.md). After a simulated stop from compound A to B, the fresh-tyre pace is `recent − deg_A × tyre_age_now + offset(B) − offset(A)`. Reason: without it a stop onto HARD looks as fast as onto SOFT, so every stop looked cheaper than it is.

### Common random numbers and pit-lap plans in strategy

**Supersedes**: prediction-and-events / Seeded Monte Carlo strategy simulation

Candidates are unchanged: "pit on lap N+k" for k in {1, 3, 5, 8} while N+k < `total_laps − 1`, plus "no further stop" only when the driver has used two dry compounds. Each simulated lap time is base pace plus degradation times tyre age minus fuel gain plus noise; pitting resets tyre age, fits HARD (MEDIUM when on HARD), uses the guarded compound slope of the next compound and the compound pace offset, and adds the pit loss (median observed pit cost up to lap N, fallback 22.0 s). Noise is normal with the driver's clean-lap residual standard deviation (minimum 0.2 s); default 1000 runs, seed 42. New: all candidates in one call share the same random draws per run (common random numbers), so `win_probability` measures the plans' difference rather than independent noise.

A new public function `simulate_pit_laps(laps, total_laps, driver, lap, pit_laps, runs, seed)` simulates any list of pit laps (and `None` for no stop) with the same model and the same shared draws, returning `[{pit_lap, mean_s, p10_s, p90_s}]` in input order plus `pit_loss_s`; `simulate()` builds its candidates on it, so the same pit lap gives the same numbers in both. `strategy-charts-api` builds its pit-window curve on this function; its signature is fixed by this design. Alternative: let `strategy-charts-api` add the function. Rejected because AGENTS.md keeps strategy internals in this track.

### Safety car and virtual safety car periods

Each run of the position simulator may contain at most one neutralised period. For each lap j from N+1 to `total_laps − 2` a safety car starts with probability `SC_PROB_PER_LAP` (0.008) and a virtual safety car with `VSC_PROB_PER_LAP` (0.006), the first draw winning (estimates: about 0.45 safety cars and 0.35 virtual safety cars per 57-lap race; confirm against race-control counts on the evaluation races, recorded in tasks.md). A safety car lasts `SC_LAPS` (4) laps and a virtual safety car `VSC_LAPS` (3), truncated at the flag. During the period every lap is multiplied by `SC_LAP_FACTOR` (1.35) or `VSC_LAP_FACTOR` (1.25), dirty air is off, and the pit loss is multiplied by `SC_PIT_LOSS_FACTOR` (0.5) or `VSC_PIT_LOSS_FACTOR` (0.6). At the end of the first safety-car lap, each car's gap to the car ahead on the same lap count is reduced to at most `SC_GAP_S` (1.0 s), keeping the order. A driver who still needs a stop moves it to the period's first lap with probability `SC_PIT_PROB` (0.8). A safety car already active at lap N is not modelled (the period starts only after N). The random draws come from the same seeded generator, so results stay reproducible per lap. Reason: the user asked for it (2026-11-22), and most cheap stops and position swings happen under neutralisation, which a green-only model cannot express.

### Store the finishing-position distribution

`summarize` also returns `position_distribution`: a list whose element i is the share of runs in which the driver finished P(i+1), length = number of drivers, each list summing to 1 within 0.001. `python -m augur.analyze` stores it as a JSON text column `position_distribution` in `position_predictions`; opening an existing database without the column adds it (`ALTER TABLE … ADD COLUMN`) and old rows read as null. `ReplayStore.positions_until` returns the column only when asked (`include_distribution=True`), so the current `/positions` and `/positions/history` responses keep their exact shape. Alternative: recompute the distribution at request time. Rejected because a request would rerun the simulator (about 0.25 s per lap at 1000 runs, estimate from the 15 s Bahrain analysis).

### Podium calibration in the benchmark

`augur.scoring` adds, over the same checkpoint pairs as the podium skill: `log_loss_model` and `log_loss_baseline` (mean negative log likelihood with forecasts clipped to [0.001, 0.999], rounded to 4 decimals) and `reliability`: five bins [0, 0.2), [0.2, 0.4), [0.4, 0.6), [0.6, 0.8), [0.8, 1.0] with `count`, `mean_forecast`, `observed_rate` (null when count is 0). The bench writes them pooled and per race; the summary line does not change. Reason: the podium skill alone did not reveal that forecasts were all near 0 or 1.

### Evaluation races 2024 rounds 12 to 23 for tuning

`python -m augur.bench --model <name> --eval` scores the evaluation races 2024 rounds 12 to 23, twelve races held in a constant in `augur.bench`, with the same code and writes `bench/<name>-eval.json`; it applies the same refusals (unknown model, missing race, race in the model's `train_races`). New module `augur.tune_sim` (`python -m augur.tune_sim --model <name>`) runs the position simulator only at the checkpoint laps of the evaluation races for a grid of `PACE_OFFSET_SD_S` {0.05, 0.10, 0.15, 0.20, 0.30} × `MODEL_DELTA_DECAY` {0.3, 0.5, 0.7} and prints pooled podium Brier and log loss per combination, so the chosen constants are reproducible. The chosen values go into `augur.config` with the measured table in tasks.md. Reason: tuning on the benchmark races would make the headline score meaningless; rounds 12 to 23 are neither training (rounds 2 to 11) nor benchmark races. Alternative: no tuning, keep estimates. Rejected because the offset size directly sets calibration.

### Wave 1 backend track BE-1

This change follows the Stage 4 Wave 1 rules in `AGENTS.md`: own worktree, changes only `backend/` and `bench/`, no route or response change in `api.py`, and the `strategy.simulate()` signature stays. Tasks 1.1 (`simulate_pit_laps`) and 2.4 (stored distribution) are merged to `main` as soon as they are done, because `strategy-charts-api` waits for them. README notes are recorded in tasks.md, not applied.

## Implementation Contract

**Behavior**

- `positions_at(feed, lap, model, prior, runs, seed)` keeps its signature and output fields, plus `position_distribution` per driver. Probabilities still sum to 1 / 3 / min(10, n); results are identical for the same inputs and seed; results at lap N do not change when laps after N change.
- `strategy.simulate(...)` keeps its signature and response; `win_probability` now comes from shared draws.
- New `strategy.simulate_pit_laps(laps, total_laps, driver, lap, pit_laps, runs=1000, seed=42) -> {"pit_loss_s": float, "plans": [{"pit_lap": int | None, "mean_s", "p10_s", "p90_s"}]}`. Plans keep input order. A pit lap outside [N+1, total_laps − 2] raises `ValueError`. Returns `plans: []` when the driver has no state (same condition as `simulate`).
- New config constants (all in `augur.config`, with the estimate notes above): `MODEL_DELTA_DECAY`, `DEG_SHRINK_STINTS`, `DEG_CAP_S_PER_LAP`, `PACE_OFFSET_SD_S`, `COMPOUND_PACE_OFFSET_S`, `SC_PROB_PER_LAP`, `VSC_PROB_PER_LAP`, `SC_LAPS`, `VSC_LAPS`, `SC_LAP_FACTOR`, `VSC_LAP_FACTOR`, `SC_PIT_LOSS_FACTOR`, `VSC_PIT_LOSS_FACTOR`, `SC_GAP_S`, `SC_PIT_PROB`.
- `bench/<name>.json` gains `log_loss_model`, `log_loss_baseline`, `reliability` (pooled and per race). `bench/<name>-eval.json` has the same shape for the evaluation races.
- `python -m augur.tune_sim --model <name>` prints one line per grid combination: `offset_sd=<x> decay=<y> brier=<b> log_loss=<l>`.

**Failure modes**

- Evaluation race not ingested: `missing race <race_id>, run augur.ingest first`, exit 1, no file (same as the bench).
- Old database without `position_distribution`: the column is added on open; old rows return null distribution until re-analysis.

**Acceptance**

- Tests named in tasks.md pass, plus the existing suite (403 backend tests on the polish worktree, 2026-11-21) except tests whose asserted numbers change because of the new model; each such test is updated with the new expected value and a note in tasks.md.
- Measured after re-analysis and recorded in tasks.md: pooled and per-race podium skill for `lightgbm` and `baseline`, extreme-forecast share per benchmark race, Bahrain lap 14 favourites, evaluation-race scores, and the number of cached commentary texts that no longer pass the grounding check.

**Scope**

- In: `augur.positions`, `augur.strategy`, `augur.models.degradation` (new function only), `augur.config`, `augur.scoring`, `augur.bench`, new `augur.tune_sim`, `augur.analyze` and the `position_predictions` schema, `ReplayStore.positions_until`, `bench/`.
- Out: `augur.api` routes and responses, frontend, README, features and training, event detector rules.

## Risks / Trade-offs

- [The target podium skill above 0% is not reached] → Report the measured numbers anyway (AGENTS.md forbids invented metrics); record what was tried and the next hypothesis in tasks.md.
- [Constants tuned on 12 races still overfit] → Tune only two constants on a coarse grid; keep all others as documented estimates.
- [Safety-car constants are guesses] → One period per run and fixed factors keep the effect bounded; tasks.md compares the simulated rate with race-control counts on the evaluation races.
- [Re-analysis changes event `next` texts, so cached LLM commentary quoting old strategy numbers fails grounding] → Count those texts after re-analysis; regenerating commentary is a separate `python -m augur.narrate` run the user starts.
- [Ingesting rounds 12 to 23 needs network and the OpenF1 rate limit] → About 575 s for 22 races was measured on 2026-11-19, so about 5 min is expected for the twelve races (estimate); the response cache makes reruns offline.
- [`strategy-charts-api` waits on tasks 1.1 and 2.4] → Those are early tasks and are merged to `main` as soon as they pass.
