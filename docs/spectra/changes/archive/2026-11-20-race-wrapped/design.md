## Context

After `prediction-and-events` and `position-prediction`, analysis stores events and per-lap finishing-position probabilities per race and model in SQLite, and models implement the `LapTimeModel` protocol with a `name` and `author`. After `race-dashboard`, the dashboard has a status bar, Tailwind design tokens taken from BENNNZO/f1-dashboard, and a focus driver. The user wants AUGUR to be cloned and improved by others, who then show off their model's accuracy; there is no hosted site or shared leaderboard. The user chose: Wrapped as full-screen story cards, downloadable in Instagram story size, unlocked at the final lap; a benchmark on 2024 rounds 1 and 24 whose headline score measures finishing-position prediction, with lap-time MAE and event hit rate as further scores.

## Goals / Non-Goals

**Goals:**

- Every undercut and degradation call is marked hit, miss, or void with a one-sentence reason.
- Replaying never reveals an outcome before its deciding lap.
- One command gives any model a comparable, reproducible score.
- Seven Wrapped cards that read well as 1080×1920 images.

**Non-Goals:**

- Outcomes for `pace_drop`, `overcut_window`, and `position_change`.
- A hosted website, online leaderboard, or upload of results.
- Contribution guide or public repository setup (the repository stays private for now).
- Video export, animated cards, or posting to social networks.
- "Download all" as a zip (change `polish`, Stage 3).
- Wrapped before the final lap or for a race that was not analyzed.

## Decisions

### Outcomes resolved at analyze time, revealed by lap

`augur.analyze` computes each outcome right after detection using the full race, because outcomes are about the future by definition, and stores `outcome`, `outcome_lap` (the lap at which it was decided), and `outcome_text`. `/events?lap=N` returns these fields only when `outcome_lap <= N`; otherwise all three are null, meaning pending. Alternative: compute outcomes in the API from laps up to N. Rejected because it repeats work on every request and spreads future-data reads into the API.

Rules (window `OUTCOME_WINDOW_LAPS = 8`, estimate):

| Event | Hit | Miss | Void |
|---|---|---|---|
| `undercut_window` at lap E, chaser C behind target T | C is ahead of T at lap E+8 | C is not ahead of T at lap E+8 | the race ends before lap E+8 |
| `degradation_warning` at lap E for driver D | D pits (a `pit_in` lap) on a lap in E+1..E+8 | D completes lap E+8 without pitting | the race ends before lap E+8 |

`outcome_lap` is E+8 for undercut hits and misses and for degradation misses, the pit lap for a degradation hit, and `total_laps` for void.

### Podium skill against current order is the headline score

Finishing-position prediction is AUGUR's headline output, so the headline score measures it. Checkpoints are laps `floor(0.25 × total_laps)`, `floor(0.5 × total_laps)`, and `floor(0.75 × total_laps)`. At each checkpoint c and for each driver d, the model's forecast is `p_podium(c, d)` from `position_predictions`; the baseline forecast is 1 when d is in P1-P3 at c and 0 otherwise ("current order holds"); the outcome is 1 when d finishes P1-P3. `brier_model` and `brier_baseline` are the mean squared errors over all (c, d) pairs, and `position_skill_pct = 100 × (1 − brier_model / brier_baseline)` rounded to 1 decimal, or null when `brier_baseline` is 0 (the podium never changed after the first checkpoint). Alternative: exact finishing-position accuracy. Rejected because it ignores probability calibration and punishes honest uncertainty.

### Shared scoring for bench and Wrapped

`augur.scoring` computes, for one race and one model: the podium skill above; `mae_model_s` and `mae_baseline_s` over clean laps with a prediction and `lap_improvement_pct = 100 × (mae_baseline_s − mae_model_s) / mae_baseline_s` rounded to 1 decimal; and the hit rate `{undercut: {hits, resolved}, degradation: {hits, resolved}, hits, resolved, overall_pct}` (top-level `hits` and `resolved` are the totals over both types), where resolved counts hits and misses and excludes voids. A pooled variant combines races by pooling (c, d) pairs, clean laps, and events. Both `augur.bench` and the Wrapped endpoint call it, so the numbers always match.

### Fixed benchmark races

The benchmark races are `2024-01-bahrain-grand-prix` and `2024-24-abu-dhabi-grand-prix`. `augur.bench` refuses a model whose metrics file lists either race in `train_races`. Results record `seed` 42, `data_source` "openf1", and `augur_version` (`augur.__version__`) so others can reproduce them.

### Story cards rendered as DOM and exported with html-to-image

Each card is a React component laid out on a 1080×1920 logical canvas and scaled to fit the viewport with a CSS transform. Download uses html-to-image `toPng` on the unscaled card node with `width` 1080, `height` 1920, and `pixelRatio` 1, after `document.fonts.ready`. File name: `augur-wrapped-<race_id>-<n>-<card>.png`. Alternative: server-side image rendering. Rejected because it adds a browser or image stack to the backend.

### Card accent colours

Cards reuse the dashboard tokens (zinc-950 background, JetBrains Mono) with large type and one accent per card: 1 Summary = winner's team colour, 2 Podium Call = `#fbcc1c`, 3 Accuracy = `emerald-400` when `position_skill_pct > 0` else `#f12f32`, 4 Best Call = `purple-400`, 5 Biggest Miss = `#f12f32`, 6 Biggest Moment = `zinc-300`, 7 Driver = that driver's team colour. Every card footer reads `AUGUR · <model name> by <author> · <event name> <year>`.

## Implementation Contract

**Commands**

- `python -m augur.bench --model <name>` → analyzes both benchmark races with that model when they have no events or position predictions for it (or their undercut and degradation events have no outcome, i.e. were stored before outcomes existed), writes `bench/<name>.json` = `{model, author, races, position_skill_pct, brier_model, brier_baseline, lap_improvement_pct, mae_model_s, mae_baseline_s, hit_rate, per_race: [{race_id, position_skill_pct, brier_model, brier_baseline, lap_improvement_pct, mae_model_s, mae_baseline_s, hit_rate}], seed, data_source, augur_version, generated_at}`, and prints `<name>: podium skill <s>% vs current order, lap times <beat|trail> baseline by <x>%, event hit rate <y>% (<hits>/<resolved>)` (`podium skill n/a` when null; `lap times match baseline (0.0%)` when the improvement is 0.0). Exit 1 with `benchmark race <race_id> is in the training set`, `unknown model <name>`, or `missing race <race_id>, run augur.ingest first`.

**HTTP API**

- `/events?lap=N` events gain `outcome` (`"hit" | "miss" | "void" | null`), `outcome_lap`, `outcome_text`, all null until `outcome_lap <= N`.
- `GET /api/races/{race_id}/wrapped?lap=N&driver=CODE` → 409 `{"detail": "wrapped unlocks at the final lap"}` when N < `total_laps`; 409 `{"detail": "race not analyzed"}` when there are no events or position predictions for the `AUGUR_MODEL` model; 404 for an unknown race or driver. Otherwise `{race_id, event_name, year, model: {name, author}, summary: {winner, podium, total_laps, n_events, n_events_by_type}, podium_call: {lap, predicted: [{code, p_podium}], actual: [code], correct}, score: {position_skill_pct, brier_model, brier_baseline, lap_improvement_pct, mae_model_s, mae_baseline_s}, hit_rate, best_call, biggest_miss, biggest_moment, driver: {code, team, team_color, grid_position, final_position, positions_by_lap, p_podium_by_lap, stints: [{compound, laps}], events}}`. `podium_call` uses the middle checkpoint `floor(0.5 × total_laps)`: the three drivers with the highest `p_podium` there, the actual podium, and how many of the three are on it. `best_call` is the hit with the highest severity (ties: earliest lap), `biggest_miss` the miss with the highest severity, `biggest_moment` the event with the highest severity; each is null when none exists.

**Frontend**

- Status bar shows a "Wrapped" button, disabled with a lock icon until lap = `total_laps` (and while no focus driver is set); enabled, it opens a full-screen overlay for the current race, model, and focus driver.
- Overlay: 7 progress segments at the top; Right arrow or click on the right half goes forward, Left arrow or left half goes back, Esc closes; button "Download card".
- Cards: 1 Summary (event, winner, podium, laps, event count), 2 Podium Call ("At lap 29 AUGUR's podium was A, B, C — 2 of 3 correct" with each probability), 3 Accuracy (podium skill, lap-time improvement, hit rate), 4 Best Call, 5 Biggest Miss, 6 Biggest Moment (each showing lap, drivers, title, what AUGUR said, and the outcome text where present), 7 Driver (grid (when `grid_position` is null, as with OpenF1 data, the position after lap 1, labelled "Lap 1") → final position, position line by lap, podium-probability line by lap, stint bar, their events with outcomes). A null section shows "No resolved calls this race" or "No events this race".

**Acceptance**

- `pytest backend` covers outcome rules, outcome hiding, scoring, bench refusal, and wrapped responses on fixtures.
- `npm --prefix frontend run test` covers the button lock, navigation, and that download produces a 1080×1920 PNG (mocked html-to-image called with those sizes).
- Manual: `python -m augur.bench --model lightgbm` writes `bench/lightgbm.json`; at the final lap of `2024-24-abu-dhabi-grand-prix` the Wrapped opens and a downloaded PNG is 1080×1920.

**Scope**

- In: outcomes, scoring, bench command, wrapped endpoint, Wrapped overlay and single-card export, README section "Benchmark your model".
- Out: new event types, outcome rules for other types, zip export, hosting, social posting.

## Risks / Trade-offs

- [The 8-lap window is an estimate] → named constant `OUTCOME_WINDOW_LAPS`; check the hit/miss/void counts on both demo races before finalizing.
- [Degradation "hit" measures whether the team pitted, not whether the tyres truly fell off] → stated in `outcome_text` ("D pitted on lap X, 5 laps after the warning").
- [A podium that never changes makes the skill undefined] → reported as null and shown as "Order never changed — nothing to beat".
- [Two races give a noisy benchmark] → always show the raw Brier pair and `hits/resolved` next to percentages.
- [html-to-image misses web fonts in exported PNGs] → use the JetBrains Mono the dashboard already loads through `@fontsource-variable/jetbrains-mono` and wait for `document.fonts.ready` before export.
