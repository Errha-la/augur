## 1. Grid engine and board model

- [x] 1.1 Implement the grid engine in `frontend/src/canvas/grid.ts` ("Own grid engine instead of a library"): collision, upward compaction with one fixed widget, clamping to 12 columns and type minimums, cell-to-pixel conversion. Verify with Vitest cases for the "Push down on drop" example (A ends at (0,6)), "Compaction after removal", and "Keyboard resize respects the minimum" in `frontend/src/canvas/grid.test.ts`.
- [x] 1.2 Add the widget registry and board model ("Widget instances with settings"): the five types with title, default and minimum size, settings schema; board and widget types from the design's data shapes; the 24-widget cap. Verify with Vitest cases for "Same type twice" (distinct ids) and "Board full" in `frontend/src/canvas/board.test.ts`. [after: 1.1]
- [x] 1.3 Define the three presets from the design's presets table ("Presets and custom boards") and check each preset's geometry has no overlap and respects minimums. Verify with a Vitest case per preset in `frontend/src/canvas/presets.test.ts`. [after: 1.2]

## 2. Board on screen

- [x] 2.1 Replace `Layout` with `Board` and `WidgetFrame` for the "Board grid" requirement ("Boards of widgets on a snap grid"): status bar unchanged on top, widgets placed from the board, drag by title bar, resize by corner with a snapped placeholder, keyboard move and resize, single column below 760 px. Wrap the existing panels as the five widget types, keeping their `data-testid` values on widget bodies; move `Layout.test.tsx` assertions to `frontend/src/components/Board.test.tsx` and delete `Layout.tsx`. Verify with Board tests for pointer drag (placeholder then drop), keyboard move, the "Narrow screen" scenario, and the full existing frontend suite. [after: 1.3]
- [x] 2.2 Add "+ Widget" and the remove button for the "Widget instances" requirement. Verify with Board tests for adding a second `driver` widget, removing a widget (compaction), and the "A board holds at most 24 widgets" message. [after: 2.1]

## 3. Widget settings

- [x] 3.1 Add the per-widget driver setting for the "Per-widget driver" requirement ("Per-widget driver with follow-focus default"): title-bar picker, `FocusPanel` and `LapChart` take the widget's driver, missing-driver message, highlights still follow the focus driver, and a shared request cache by URL cleared on race change. Verify with Vitest cases for "Two pinned lap charts", "Pinned driver missing", and "Shared request" (one `/strategy?lap=20&driver=NOR` call with the fake backend), plus the existing `FocusPanel` and `LapChart` tests. [after: 2.2]
- [x] 3.2 Add the "Event type filter" to the `events` widget: chips in the title bar, filtered primary card and history, "No matching events yet". Verify with the "Filtered primary event" scenario test and the existing `IntelligencePanel` tests. [after: 3.1]
- [x] 3.3 Make event text scale with the widget for the "Text scales with the widget" requirement ("Text that scales with the widget"): container queries on widget bodies, no maximum line length, clamp sizes for commentary, title, and body. Verify with a test that the commentary has no max-width class and uses the container-scaled class, and with screenshots of one event at 3, 6, and 12 columns against the real backend, saved paths recorded here. [after: 3.2]

## 4. Boards, persistence, export and import

- [x] 4.1 Add the board menu for the "Presets" and "Custom boards" requirements: switch boards, "edited" marker, Reset to preset, New blank board, Rename, Duplicate, Delete with in-page confirmation. Verify with Vitest cases for "Reset an edited preset", "Blank board", and "Delete active board". [after: 3.3]
- [x] 4.2 Persist boards for the "Board persistence" requirement ("Boards in localStorage with JSON export and import"): save within 300 ms, restore on load, corrupted-storage and storage-unavailable notices. Verify with Vitest cases for "Reload keeps a custom board", "Corrupted storage" (stored value unchanged), and a storage that throws. [after: 4.1]
- [x] 4.3 Add Export and Import for the "Board export and import" requirement: file name, file format, validation, 100 KB limit, clamping, report message. Verify with Vitest cases for "Round trip", "Unknown widget type" (2 widgets, 1 skipped), "Wrong file", and a 101 KB file. [after: 4.2]

## 5. Guide and release check

- [x] 5.1 Add the "First-visit guide" ("First-visit guide"): four anchored steps, Back, Next, Done, Skip, Escape, `augur.guide.v1`, "?" button in the status bar, keyboard focus, reduced motion. Verify with Vitest cases for "First visit" and "Reopen" and a keyboard-only walk through the four steps. [after: 4.3]
- [x] 5.2 Manual check against the real backend from this worktree ("Wave 1 frontend track"): drag, resize, keyboard move, two `lapchart` widgets pinned to LEC and PIA, a custom board surviving reload, export then import, the guide, the 700 px single-column view, and a 24-widget board during 4× playback (record whether playback keeps one lap per 250 ms). Record results and README notes for `portfolio-release` here. Verify with `npm --prefix frontend run test` and `npm --prefix frontend run build` passing. [after: 5.1]

## Results (2026-11-22)

### 3.3 Text scaling screenshots

Real backend, 2024 Abu Dhabi lap 20, `events` widget with every type shown (glm commentary). Commentary font size and width measured in Chromium:

| Widget width | Commentary font | Commentary width / widget body | Horizontal scroll | Screenshot |
|---|---|---|---|---|
| 3 columns | 13.1 px | 284 / 348 px | no | `~/drafts/augur-screenshots/dashboard-canvas/events-3col.png` |
| 6 columns | 14.8 px | 642 / 706 px | no | `~/drafts/augur-screenshots/dashboard-canvas/events-6col.png` |
| 12 columns | 18 px (max) | 1358 / 1422 px | no | `~/drafts/augur-screenshots/dashboard-canvas/events-12col.png` |

### 5.2 Manual check against the real backend

Backend from the main checkout (`AUGUR_NARRATOR=openai_compat AUGUR_LLM_MODEL=glm`), Vite from this worktree, Chromium driven by Playwright at 1440×1000. All passed, no page errors:

- Guide opens on a first visit; four steps anchored to title bar, resize corner, + Widget, board menu; stays closed after Done and reload; "?" reopens step 1; Escape closes. Screenshot: `~/drafts/augur-screenshots/dashboard-canvas/guide-step1.png`.
- Pointer drag (BATTLE timeline 0,13 → 0,5) with the dashed placeholder; corner resize 7×6 → 5×7; keyboard ArrowDown / Shift+ArrowRight move and resize without changing the lap.
- Custom board "Board 1" with two `lapchart` widgets pinned to LEC and PIA and a timing list: charts plot LEC and PIA while the NOR row is highlighted. Screenshot: `~/drafts/augur-screenshots/dashboard-canvas/two-lapcharts.png`.
- Reload keeps Board 1, both positions, and both pins.
- Export downloads `augur-board-board-1.json`; importing it reports "Imported Board 1: 3 widgets, 0 skipped" with the same cells.
- 700 px viewport: one column, no resize corners, no horizontal page scroll. Screenshot: `~/drafts/augur-screenshots/dashboard-canvas/narrow-700.png`.
- 4× playback (6 s window): BATTLE ≈ 511 ms per lap; a 24-widget board (10 pinned driver/lap-chart widgets) ≈ 955 ms per lap. **Neither keeps one lap per 250 ms**: playback waits for each lap's five responses before advancing, so 4× is bounded by the backend even on a preset board; 24 widgets roughly halve it again (rendering 24 panels per lap). The 24-widget cap stays; a faster 4× needs prefetching the next lap (out of scope here).
- `npm --prefix frontend run test`: 29 files, 200 tests pass. `npm --prefix frontend run build`: passes (existing >500 kB chunk warning).

Screenshots are kept outside the repository (`~/drafts/augur-screenshots/dashboard-canvas/`, six PNG files) and are not committed: this frontend track changes only `frontend/` (`AGENTS.md`), and `portfolio-release` (Wave 4) takes the repository screenshots. Decided by the user on 2026-11-23.

### Deviations from the first spec text (resolved 2026-11-23)

- Board persistence: a **missing** `augur.boards.v1` (first visit) starts from the presets **without** the "Saved boards could not be read" notice; the notice is shown only for a stored value that is unreadable or another version. The spec text lists "missing" with the notice, which would show an error to every first-time visitor. Resolved 2026-11-23: the spec and design now say a first visit shows no notice (scenario "First visit without a notice", covered by "a first visit with nothing stored starts on BATTLE without a notice" in `BoardPersistence.test.tsx`).
- Restoring and importing boards resolve overlaps by pushing widgets down only (no upward compaction), so gaps the viewer left survive a reload and an export → import round trip ("Round trip" requires the same positions). Resolved 2026-11-23: the spec and design now say restore and import push overlapping widgets down only; `BoardFiles.test.tsx` adds "import keeps a gap in the file instead of compacting it upward". It fails when import compacts upward (checked by swapping `separate` for `compact` in `sanitize.ts`); with it the frontend suite is 29 files, 201 tests, and the build passes (2026-11-23).

### Known issue found during the manual check (not part of this change)

Stored glm commentary (`openai_compat`, `glm`, en) for 2024 Abu Dhabi has stray tokens in 8 of 116 events: CJK ("丰富润色", "从前", "择要", "丘"), Cyrillic, Polish ("księga"), and words glued to driver codes ("ALOtekst", "ALOdesk", "theScripted", "thistracks"). Grounding checks only numbers and driver codes, so these pass. User decision 2026-11-22: treat as a model-quality issue, record it as a known issue for `portfolio-release`, and compare with the Gemini narrator; no grounding change now.

### README notes for `portfolio-release`

- Boards: PIT WALL, BATTLE (default), PACE, plus your own blank boards; drag by the title bar, resize from the corner, arrow keys move and Shift+arrow keys resize a focused widget.
- "+ Widget" adds Timing, Events, Driver, Lap times, Timeline; the same widget can be added more than once, and Driver / Lap times widgets each pick a driver or follow the focus driver.
- Boards are saved only in this browser (`localStorage`, key `augur.boards.v1`); share them with Export / Import (`augur-board-<name>.json`, max 100 KB, 24 widgets).
- "?" in the status bar reopens the four-step guide.
