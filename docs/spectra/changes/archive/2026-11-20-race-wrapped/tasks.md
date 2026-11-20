## 1. Event outcomes

- [x] 1.1 Implement the Undercut outcome and Degradation outcome rules in `augur.events.outcomes` following Outcomes resolved at analyze time, revealed by lap (`OUTCOME_WINDOW_LAPS = 8` in `augur.config`, hit/miss/void, `outcome_lap`, one-sentence `outcome_text`), add nullable `outcome`, `outcome_lap`, `outcome_text` columns to the `events` table, and call the resolver from `python -m augur.analyze`. Verify: unit tests for every row of the undercut "outcome table" and the "pit on lap 23" and "No pit inside the window" cases in specs/event-outcomes.
- [x] 1.2 [after: 1.1] Make Outcomes hidden until resolved: `/events?lap=N` returns the three outcome fields only when `outcome_lap <= N`, and null for event types without an outcome rule. Verify: TestClient test for every row of the "hit decided on lap 23" table and a `position_change` event that always returns null outcome.

## 2. Scoring and benchmark

- [x] 2.1 Implement the Podium skill score following Podium skill against current order is the headline score: checkpoints at `floor` of 25/50/75% of `total_laps`, model and "current order holds" baseline Brier scores from `position_predictions`, skill rounded to 1 decimal, null when the baseline Brier is 0. Verify: unit tests for the "Checkpoint laps" table, the "one checkpoint, four drivers" example (0.165, 0.5, 67.0), and "Podium never changed".
- [x] 2.2 [after: 1.1, 2.1] Implement Shared scoring for bench and Wrapped in `augur.scoring`: per race and pooled podium skill, `mae_model_s`, `mae_baseline_s`, `lap_improvement_pct`, and hit rate excluding voids. Verify: unit test reproducing the "pooled scores" example values (40.0%, 18.0%, 9/14).
- [x] 2.3 [after: 2.2] Implement `python -m augur.bench --model` to Score a model on the benchmark races using Fixed benchmark races (2024 rounds 1 and 24): analyze races lacking events or position predictions for the model, write `bench/<name>.json` with every listed key including `seed` 42, `data_source` "openf1", and `augur_version`, print the summary line with beat/trail and `n/a` forms. Verify: test on two synthetic benchmark-race stand-ins asserting the JSON keys and the "pooled scores" printed line; "Same model twice" test comparing files except `generated_at`.
- [x] 2.4 [after: 2.3] Enforce Benchmark races excluded from training plus the unknown-model and missing-race errors, writing no file on failure. Verify: test for "Trained on a benchmark race" and one test per other error message.

## 3. Wrapped API

- [x] 3.1 [after: 1.2, 2.2] Implement `GET /api/races/{race_id}/wrapped` with Wrapped unlocks at the final lap (409 locked, 409 not analyzed, 404 race/driver). Verify: TestClient test for every row of the "58-lap race" table and the not-analyzed case.
- [x] 3.2 [after: 3.1] Fill the Wrapped content: summary with winner and podium at the final lap, the podium call at the middle checkpoint, scores from `augur.scoring`, hit rate, highlight selection with severity then earliest-lap tie-breaking, and the driver block (grid and final position, positions and `p_podium` by lap, stints, events with outcomes). Verify: TestClient tests for the "four events" and "two of three" examples and the "Score matches the bench" scenario on fixtures.

## 4. Wrapped story in the dashboard

- [x] 4.1 [after: 3.2] Add the Wrapped entry point button to the status bar (locked until the final lap) and a typed client call for `/wrapped` with the focus driver. Verify: component test for "Unlock at the final lap" with mocked fetch.
- [x] 4.2 [after: 4.1] Implement the Story card sequence overlay: 7 cards on a 1080×1920 logical canvas scaled to the viewport, progress segments, keyboard and half-screen click navigation, Esc to close, Card accent colours, footer text, and empty-state texts. Verify: component tests for every row of the "key presses" table, the "Accuracy card" and "Podium Call card" scenarios, and the empty-state texts when highlights or the skill are null.
- [x] 4.3 [after: 4.2] Implement Story card download following Story cards rendered as DOM and exported with html-to-image: "Download card" via `toPng` at 1080×1920 with pixelRatio 1 after `document.fonts.ready`, with the specified file name; use the JetBrains Mono already loaded through `@fontsource-variable/jetbrains-mono`. Verify: component test with mocked html-to-image asserting the size, the call happening after fonts are ready, and the "Card export size" file name.

## 5. End-to-end check

- [x] 5.1 [after: 2.4, 4.3] Run `python -m augur.train --model baseline`, then `python -m augur.bench --model lightgbm` and `--model baseline`, add a README section "Benchmark your model" with both summary lines and a link to `docs/swap-model.md`, update that document's step 6 and error table to the real `augur.bench` output, and remove its "Status" note once every step is verified, then replay `2024-24-abu-dhabi-grand-prix` to the final lap, open the Wrapped, and download every card. Verify: `bench/lightgbm.json` and `bench/baseline.json` exist (baseline `lap_improvement_pct` is 0.0); each downloaded PNG is 1080×1920 checked with `file`; `pytest backend` and `npm --prefix frontend run test` pass.

Run notes for 5.1 (2026-11-20): run on a copy of the main checkout's `data/` (models, races, catalog), so the real data directory was not changed; `bench/*.json` are committed.

- `python -m augur.train --model baseline` → `baseline: mae_model_s=0.3802 mae_baseline_s=0.3802 (n_train=8161, n_test=1773)`.
- `python -m augur.bench --model lightgbm` (re-analyzed both races: their events predated outcomes, about 33 s) → `lightgbm: podium skill -15.9% vs current order, lap times beat baseline by 19.8%, event hit rate 44% (61/137)`.
- `python -m augur.bench --model baseline` → `baseline: podium skill 61.7% vs current order, lap times match baseline (0.0%), event hit rate 44% (61/137)`. `bench/baseline.json` has `lap_improvement_pct` 0.0.
- Hit / miss / void with `lightgbm` (8-lap window): Bahrain undercut 17/18/5, degradation 17/22/9; Abu Dhabi undercut 20/14/8, degradation 7/22/3. The window stays at 8 laps.
- README section "Benchmark your model" added; `docs/swap-model.md` step 6 and the bench errors in section 5 now show the real output. Its Status note stays, reduced to step 5's settings panel, which comes with `polish` (not every step is verified yet).
- Browser (headless Chromium, `AUGUR_MODEL` lightgbm): Abu Dhabi, WRAPPED locked at laps 1 and 57 (`/wrapped?lap=57` → 409), enabled at 58; all 7 cards downloaded, `file` reports `PNG image data, 1080 x 1920` for each; JetBrains Mono renders in the PNGs (variable font embedded); Esc closes; no console errors.
- Fixed while checking: Driver card showed `P?` (OpenF1 ingest stores no grid, so `grid_position` is always null; the card now shows the lap 1 position labelled "Lap 1"), the position line was upside down, and per-race skill printed `-0.0`.
- `pytest backend` → 292 passed, 1 skipped; `npm --prefix frontend run test` → 14 files, 98 tests passed; `npm --prefix frontend run build` succeeds.
- Deviations to review: a bench re-analyzes races whose outcome-type events have no outcome (stored before this change), in addition to the spec's "no events or position predictions"; a tie prints `lap times match baseline (0.0%)` instead of beat/trail.
- Finding for `position-prediction` (not fixed here): with `lightgbm` the position simulator scores worse than "current order holds" (-15.9%), e.g. Abu Dhabi lap 13 HUL (P7) `p_win` 0.828, lap 20 LEC (P4, +21 s) `p_win` 0.854; with `baseline` the same laps are sane (NOR `p_win` 0.868 at lap 20).
