## 1. Event outcomes

- [ ] 1.1 Implement the Undercut outcome and Degradation outcome rules in `augur.events.outcomes` following Outcomes resolved at analyze time, revealed by lap (`OUTCOME_WINDOW_LAPS = 8` in `augur.config`, hit/miss/void, `outcome_lap`, one-sentence `outcome_text`), add nullable `outcome`, `outcome_lap`, `outcome_text` columns to the `events` table, and call the resolver from `python -m augur.analyze`. Verify: unit tests for every row of the undercut "outcome table" and the "pit on lap 23" and "No pit inside the window" cases in specs/event-outcomes.
- [ ] 1.2 [after: 1.1] Make Outcomes hidden until resolved: `/events?lap=N` returns the three outcome fields only when `outcome_lap <= N`, and null for event types without an outcome rule. Verify: TestClient test for every row of the "hit decided on lap 23" table and a `position_change` event that always returns null outcome.

## 2. Scoring and benchmark

- [ ] 2.1 Implement the Podium skill score following Podium skill against current order is the headline score: checkpoints at `floor` of 25/50/75% of `total_laps`, model and "current order holds" baseline Brier scores from `position_predictions`, skill rounded to 1 decimal, null when the baseline Brier is 0. Verify: unit tests for the "Checkpoint laps" table, the "one checkpoint, four drivers" example (0.165, 0.5, 67.0), and "Podium never changed".
- [ ] 2.2 [after: 1.1, 2.1] Implement Shared scoring for bench and Wrapped in `augur.scoring`: per race and pooled podium skill, `mae_model_s`, `mae_baseline_s`, `lap_improvement_pct`, and hit rate excluding voids. Verify: unit test reproducing the "pooled scores" example values (40.0%, 18.0%, 9/14).
- [ ] 2.3 [after: 2.2] Implement `python -m augur.bench --model` to Score a model on the benchmark races using Fixed benchmark races (2024 rounds 1 and 24): analyze races lacking events or position predictions for the model, write `bench/<name>.json` with every listed key including `seed` 42, `data_source` "openf1", and `augur_version`, print the summary line with beat/trail and `n/a` forms. Verify: test on two synthetic benchmark-race stand-ins asserting the JSON keys and the "pooled scores" printed line; "Same model twice" test comparing files except `generated_at`.
- [ ] 2.4 [after: 2.3] Enforce Benchmark races excluded from training plus the unknown-model and missing-race errors, writing no file on failure. Verify: test for "Trained on a benchmark race" and one test per other error message.

## 3. Wrapped API

- [ ] 3.1 [after: 1.2, 2.2] Implement `GET /api/races/{race_id}/wrapped` with Wrapped unlocks at the final lap (409 locked, 409 not analyzed, 404 race/driver). Verify: TestClient test for every row of the "58-lap race" table and the not-analyzed case.
- [ ] 3.2 [after: 3.1] Fill the Wrapped content: summary with winner and podium at the final lap, the podium call at the middle checkpoint, scores from `augur.scoring`, hit rate, highlight selection with severity then earliest-lap tie-breaking, and the driver block (grid and final position, positions and `p_podium` by lap, stints, events with outcomes). Verify: TestClient tests for the "four events" and "two of three" examples and the "Score matches the bench" scenario on fixtures.

## 4. Wrapped story in the dashboard

- [ ] 4.1 [after: 3.2] Add the Wrapped entry point button to the status bar (locked until the final lap) and a typed client call for `/wrapped` with the focus driver. Verify: component test for "Unlock at the final lap" with mocked fetch.
- [ ] 4.2 [after: 4.1] Implement the Story card sequence overlay: 7 cards on a 1080×1920 logical canvas scaled to the viewport, progress segments, keyboard and half-screen click navigation, Esc to close, Card accent colours, footer text, and empty-state texts. Verify: component tests for every row of the "key presses" table, the "Accuracy card" and "Podium Call card" scenarios, and the empty-state texts when highlights or the skill are null.
- [ ] 4.3 [after: 4.2] Implement Story card download following Story cards rendered as DOM and exported with html-to-image: "Download card" via `toPng` at 1080×1920 with pixelRatio 1 after `document.fonts.ready`, with the specified file name; use the JetBrains Mono already loaded through `@fontsource-variable/jetbrains-mono`. Verify: component test with mocked html-to-image asserting the size, the call happening after fonts are ready, and the "Card export size" file name.

## 5. End-to-end check

- [ ] 5.1 [after: 2.4, 4.3] Run `python -m augur.train --model baseline`, then `python -m augur.bench --model lightgbm` and `--model baseline`, add a README section "Benchmark your model" with both summary lines and a link to `docs/swap-model.md`, update that document's step 6 and error table to the real `augur.bench` output, and remove its "Status" note once every step is verified, then replay `2024-24-abu-dhabi-grand-prix` to the final lap, open the Wrapped, and download every card. Verify: `bench/lightgbm.json` and `bench/baseline.json` exist (baseline `lap_improvement_pct` is 0.0); each downloaded PNG is 1080×1920 checked with `file`; `pytest backend` and `npm --prefix frontend run test` pass.
