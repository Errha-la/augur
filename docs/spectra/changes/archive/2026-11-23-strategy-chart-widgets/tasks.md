## 1. API client, registry, and shared chart plumbing

- [x] 1.1 Add typed client functions `fetchTrace`, `fetchRejoin`, `fetchPitWindow`, `fetchStints`, `fetchDegradation`, and `fetchPositionDistribution` that go through the shared request cache with an `AbortSignal`, with response types matching the `strategy-charts-api` Implementation Contract field for field, and add `position_p10` / `position_p90` to the `PositionsHistoryResponse` driver entries. Verify with a new `frontend/src/api/charts.test.ts` that stubs `fetch` and asserts each URL (including `driver` for rejoin and pit-window), the typed body passthrough, and that two identical calls send one request.
- [x] 1.2 Implement "Eight chart widget types in the registry" for the "Widget instances" requirement: register `trace`, `pitclock`, `pitwindow`, `stints`, `degradation`, `pace`, `fan`, `heatmap` with the titles, default and minimum sizes, and settings from the design's Implementation Contract table; add `drivers?: string[]` to `WidgetSettings`; make the sanitizer keep at most four distinct valid codes for `pace`. Verify with the "Chart types listed" scenario in `frontend/src/components/Board.test.tsx` and the "Imported pace drivers" example in `frontend/src/components/BoardFiles.test.tsx`. [after: 1.1]
- [x] 1.3 Implement "One chart component per type with a shared data hook" and "Request schedule per widget" for the "Chart widget loading, errors, and request schedule" requirement: a `useChartData` hook in `frontend/src/components/charts/` that fetches per lap or on the `refreshesAt` schedule, keeps the last response while skipped, and returns loading and error states, plus a `ChartBody` that shows "Loading..." and "Could not load <title>"; dispatch the eight types from `App.tsx` `renderWidget` through `frontend/src/components/charts/index.tsx`, with driver types resolved by the existing per-widget driver logic. Verify with the "Pit window during playback", "Stints every lap", and "Failed request" scenarios in a new `frontend/src/components/charts/useChartData.test.tsx`. [after: 1.2]

## 2. Race-wide charts

- [x] 2.1 Build the "Race trace widget" per "Chart content": one line per driver in team colours, the focus driver thicker, caption "Reference pace <lap time>", "No laps yet" when the reference is null. Verify with the "Reference pace caption" example and "No laps yet" scenario in `frontend/src/components/charts/RaceTrace.test.tsx`. [after: 1.3]
- [x] 2.2 Build the "Tyre stints widget": rows in response order, segments from `start_lap` to `end_lap` on a 1..total_laps axis coloured by compound, letters in segments of at least 4 laps, focus row highlighted, "No laps yet" when empty. Verify with the "Running stint ends at the current lap" scenario in `frontend/src/components/charts/Stints.test.tsx`. [after: 2.1]
- [x] 2.3 Build the "Degradation widget": per-compound scatter of tyre age against fuel-corrected time, fit lines, legend "<compound> +<slope> s/lap (<n>)" or "<compound> (<count>)", larger focus points, "No laps yet" with no compounds. Verify with the "Legend entries" example in `frontend/src/components/charts/Degradation.test.tsx`. [after: 2.2]
- [x] 2.4 Build the "Position heatmap widget": drivers by P1..Pn cells with opacity equal to the share in team colour, percentages in cells of at least 10 % and on hover, "Race not analyzed" and "No distribution stored; re-run analyze" states, null rows empty. Verify with the "Cell labels" example and "Stored before the distribution existed" scenario in `frontend/src/components/charts/Heatmap.test.tsx`. [after: 2.3]

## 3. Driver charts

- [x] 3.1 Build the "Pit clock widget" with the "Driver settings for chart widgets" rules (`driver` setting): SVG circle of `lap_length_s`, cars at `(gap mod lap length) / lap length` of a turn with "+<n>L" labels, the widget's driver ringed, rejoin marker and "Pit now: ..." text, "Pit loss <s> s", the snapshot caption, and "<code> has no gap yet". Verify with the "Rejoin text" example, "Leader rejoins in front" scenario, and "Car positions on the clock" table (via an exported angle helper) in `frontend/src/components/charts/PitClock.test.tsx`. [after: 2.4]
- [x] 3.2 Build the "Pit window widget" (`driver` setting, `refreshesAt` schedule): `delta_s` by pit lap with a p10-p90 band, "Best: lap <n>", dashed "No further stop" line, caption "Green race assumed", and the "No pit window left" / "Not enough laps yet" messages. Verify with the "Best lap and no-stop line" scenario and "Empty window messages" table in `frontend/src/components/charts/PitWindow.test.tsx`, and the "Two pit windows" scenario of the "Per-widget driver" requirement in `frontend/src/components/WidgetSettings.test.tsx`. [after: 3.1]
- [x] 3.3 Build the "Position fan widget" (`driver` setting, `refreshesAt` schedule): `expected_position` line with the `position_p10`-`position_p90` band, P1 at the top, team colour, "Race not analyzed". Verify with the "Band follows the history" and "Not analyzed" scenarios in `frontend/src/components/charts/PositionFan.test.tsx`. [after: 3.2]
- [x] 3.4 Build the "Pace comparison widget" with its `drivers` setting and title-bar picker ("Follow focus", toggle per driver, no fifth pick), focus-and-neighbours default, "<codes> not in this race", "No clean laps for <codes> yet", and the caption "Fuel-corrected clean laps". Verify with the "Follow focus", "Four drivers at most", and "Pinned driver missing" scenarios in `frontend/src/components/charts/Pace.test.tsx`. [after: 3.3]

## 4. Presets and notes

- [x] 4.1 Implement "STRATEGY preset and preset updates" for the "Presets" requirement: add the `strategy` preset id and board, swap PIT WALL `lapchart` to `pitwindow`, BATTLE `driver` to `trace`, PACE `driver` to `pace` at the same positions, keep BATTLE as the first-visit board. Verify with the "STRATEGY preset" scenario in `frontend/src/canvas/presets.test.ts` (exact widget list and positions for all four presets) and the "Stored edit survives the new definitions" and "Reset an edited preset" scenarios in `frontend/src/components/BoardPersistence.test.tsx`. [after: 3.4]
- [x] 4.2 Implement "Safety-car notes in the focus panel" for the "Focus driver panel" requirement: "Includes random safety-car and VSC periods" under the probabilities and "Assumes a green race to the end" under the strategy table. Verify with the "Safety-car notes" scenario in `frontend/src/components/FocusPanel.test.tsx`.

## 5. Real backend check and handoff

- [x] 5.1 Run the backend from `main` and the frontend from this worktree, open each preset and every chart widget on Abu Dhabi 2024 at laps 1, 20, and 58, and record per widget what it shows (or which empty state) here; play the STRATEGY board at 4× from lap 1 to 30 and record whether laps advance every 250 ms (the "Request schedule per widget" estimate); write README notes (widget list and the STRATEGY preset) for `portfolio-release` under this task. Verify that `npm --prefix frontend test` and `npm --prefix frontend run build` pass and every widget matches its spec scenario text at those laps. [after: 4.1, 4.2]

  **5.1 results (2026-11-23).** Backend from `main` (`uvicorn augur.api:app --port 8000`, `AUGUR_DATA_DIR` = main `data/`, model `lightgbm`), frontend from this worktree (Vite dev on 5173, production build via `vite preview` on 5174), headless Chromium (playwright-core 1.63), race `2024-24-abu-dhabi-grand-prix`, focus driver VER (P1 at lap 1).

  | Widget (board) | Lap 1 | Lap 20 | Lap 58 |
  |---|---|---|---|
  | Pit window (PIT WALL, STRATEGY) | "Not enough laps yet" | "Best: lap 26", 36 plans, "Green race assumed" | "No pit window left" |
  | Pit clock (STRATEGY) | 19 cars, "Pit now: rejoin P19, 17.8 s behind PIA" | 19 cars, "Pit now: rejoin P10, 1.4 s behind TSU, 0.6 s ahead of DOO", "Pit loss 22.6 s" | 16 cars, "Pit now: rejoin P7, 0.2 s behind GAS, 2.9 s ahead of HUL" |
  | Tyre stints (STRATEGY) | 20 rows | 20 rows, segments end at lap 20 | 20 rows |
  | Degradation (STRATEGY) | "No laps yet" | "MEDIUM +0.079 s/lap (196)", "HARD +0.047 s/lap (107)" | "SOFT +0.179 s/lap (24)", "MEDIUM +0.057 s/lap (243)", "HARD +0.053 s/lap (617)" |
  | Race trace (BATTLE, STRATEGY) | "Reference pace 1:39.435" | "Reference pace 1:33.153", 20 lines | "Reference pace 1:30.993", 20 lines |
  | Pace compare (PACE, follow focus) | "No clean laps for LAW, VER, HAM yet" | LEC, VER, HAM lines | RUS, VER, GAS lines |
  | Pace compare (custom, pinned VER NOR) | "No clean laps for VER, NOR yet" | VER and NOR lines | VER and NOR lines |
  | Position fan (custom) | caption "VER: expected position, band P10-P90" | line and band | line and band |
  | Position odds (custom) | 20 rows | 20 rows | 20 rows |
  | Focus panel notes (PIT WALL) | "Includes random safety-car and VSC periods" under the probabilities and "Assumes a green race to the end" under the strategy table at every lap | same | same |

  The 1.1 s / 0.6 s style pit-clock text, the pit-window messages, the degradation legend, and the reference-pace caption match their spec scenario wording. A first scripted pass read PIT WALL lap 20 before the pit-window response arrived (it still showed the lap 1 response); a recheck after the response read "Best: lap 26". Cosmetic: pit-clock code labels overlap where cars run close together.

  **4× playback** (STRATEGY from lap 1; ms per lap, measured): the 250 ms target is not met, but the replay without any widget already misses it, so this is recorded and not changed (user decision 2026-11-23: keep the every-lap schedule).

  | Board, 4× | Dev, laps 1-30 | Prod, laps 1-30 | Prod, laps 31-58 |
  |---|---|---|---|
  | Empty board (no widgets) | 351 | 354 | 377 |
  | One widget only: trace / pit clock / pit window / stints / pace / fan / odds | - | 346-358 | 369-385 |
  | One widget only: degradation | - | 372 | 440 |
  | BATTLE | 393 | 373 | 392 |
  | STRATEGY | 487 | 379 | 467 |

  Follow-up for a later change: the replay itself takes about 354 ms per lap at 4× in the production build (five per-lap requests plus render); the degradation scatter (up to about 1,800 points at lap 58) is the costliest chart. In the dev server, STRATEGY on laps 31-58 took 988 ms per lap.

  Worktree-only: Vite answered 403 for the JetBrains Mono font because `frontend/node_modules` is a symlink to the main checkout (outside Vite's allowed paths); it does not happen in the main checkout.

  `npm --prefix frontend test`: 39 files, 264 tests passed. `npm --prefix frontend run build`: passed.

  **README notes for `portfolio-release`:**

  - Strategy chart widgets (add from "+ Widget"): Race trace, Pit clock (where the driver would rejoin if it pitted now), Pit window (expected race time for a stop on every remaining lap, same simulator as the strategy table), Tyre stints, Degradation (fuel-corrected clean laps by tyre age per compound with a fitted line), Pace compare (up to four drivers), Position fan (expected finishing position with its P10-P90 band), Position odds (finishing-position probabilities per driver).
  - Presets: PIT WALL, BATTLE, PACE, and the new STRATEGY board (pit window, pit clock, tyre stints, degradation, race trace). Pit window, pit clock, and position fan follow the focus driver unless pinned.
  - Screenshot candidate: STRATEGY board on Abu Dhabi 2024 at lap 20.
