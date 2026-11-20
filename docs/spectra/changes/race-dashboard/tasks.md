## 1. App skeleton and data layer

- [x] 1.1 Scaffold `frontend/` with Vite + React + TypeScript, Tailwind CSS 4 (`@tailwindcss/vite`), Recharts, Vitest, Testing Library, and jsdom; add the Vite proxy for the API (`/api` → `http://localhost:8000`); define the Design Source tokens (colours, JetBrains Mono, easing) as Tailwind theme variables and build the Timing-screen layout after BENNNZO/f1-dashboard (status bar, timing column, intelligence area, bottom row for focus panel and chart, timeline). Verify: `npm --prefix frontend run build` succeeds and `npm --prefix frontend run test` runs a smoke test that renders the empty layout with the zinc-950 background class.
- [x] 1.2 [after: 1.1] Add a typed API client for `/races`, `/state`, `/laps`, `/predictions`, `/events`, `/strategy`, `/positions`, `/positions/history` and a `useLapData(raceId, lap)` hook that implements Fetch everything per lap with request cancellation (parallel fetch, `AbortController` for earlier laps, publish only when all five responses for the current lap arrive), plus JSON fixtures for Component tests with mocked fetch. Verify: hook tests for the "Fast slider move" and "No future requests" scenarios in specs/replay-controls.

## 2. Replay controls

- [x] 2.1 [after: 1.2] Implement Race selection and Lap navigation and playback in the status bar: race selector, slider, previous/next, Left/Right/Space keys, 1×/2×/4× playback that waits for the current lap to render before the next tick and stops at `total_laps`, plus `LAP n/total` and the track status pill coloured by `track_status`. Verify: component tests for "Switch race", every row of the "navigation cases" table using fake timers, and the pill colour for statuses 1, 4, and 5.
- [x] 2.2 [after: 2.1] Implement Backend status messages: unreachable banner with Retry, empty race list message, and the not-analyzed message with the exact texts from the spec. Verify: component tests for each message and the "Backend down then retried" scenario.

## 3. Race overview

- [x] 3.1 [after: 1.2] Implement the Timing list: rows ordered by position with team stripe, formatting rules, purple/green last-lap colouring computed from laps up to the current lap, `WIN` and `PODIUM` percentages with a podium bar per Position probabilities in the timing list and focus panel, and row click setting the focus driver. Verify: component tests for every row of the "formatted fields" table and the "two drivers" fastest-lap example; a test that clicking a row calls the focus setter with that code.
- [x] 3.2 [after: 4.1] Implement the Lap-time chart following Chart compares the focus driver with neighbours: solid actual-lap-time lines in team colours for the focus driver and the cars directly ahead and behind, gaps for null laps; focus line 3 px at full opacity, neighbour lines 1.5 px at 75% opacity, dots on a teammate neighbour's line, and a legend of driver codes titled `Neighbours at lap N`. Verify: component tests for every row of the "neighbours" table, for "Teammate neighbour", for "Neighbours follow the current lap", and for "Chart stops at the current lap", asserting no lap above the current lap is plotted.

## 4. Focus driver

- [x] 4.1 [after: 3.1] Implement Focus driver selection following One focus driver drives the detail views: default P1 at lap 1, change on row click, keep or reset on race change. Verify: component test for every row of the "focus changes" table.
- [x] 4.2 [after: 4.1] Implement the Focus driver panel: code and team, stint bar up to the current lap, degradation and cliff, predicted next lap, expected position and probabilities with the `p_win`/`p_podium` history chart and the green-race note, strategy table and probability history requested when paused or on laps divisible by 5 during playback with "Simulating..." while loading, and the driver's events. Verify: component tests for the "two stints" example, the "P5 driver at lap 30" example, and the "Strategy requests during playback" scenario using fake timers.

## 5. Intelligence panel

- [x] 5.1 [after: 1.2] Implement Primary event focus following Newest highest-severity event is primary: expanded primary card with severity bar, What / Why / Next, evidence, the strategy table with "Simulating..." for `degradation_warning` and `undercut_window`, and "No significant events yet". Verify: component tests for "Newer event takes focus" and "two events on one lap".
- [x] 5.2 [after: 5.1] Implement Collapsed event history with click-to-expand rows that never change the primary card. Verify: component tests for "Expand a history row" and "Focus driver events stay in race order".
- [x] 5.3 [after: 2.1, 5.1] Implement Event timeline navigation: markers for events up to the current lap, coloured by type, click sets the lap and stops playback. Verify: component test for "Jump to an event".
- [x] 5.4 [after: 4.1, 5.2, 5.3] Implement Focus driver highlights on the timing row, primary card, history rows, and timeline markers using the focus driver's team colour. Verify: component test for the "Highlighted event" scenario.

## 6. End-to-end check

- [x] 6.1 [after: 2.2, 3.2, 4.2, 5.4] Add README instructions for running backend and frontend together, then run both against `2024-24-abu-dhabi-grand-prix`: focus a non-leader, play laps 1 to 20 at 4×, confirm podium percentages change from lap to lap, the primary event changes when a newer event appears, the focus panel follows the driver, and the browser network log shows no request with a lap above the slider value; save one screenshot to `docs/screenshot.png`. Verify: manual checklist recorded in the task notes; `npm --prefix frontend run test` and `npm --prefix frontend run build` pass.

Run notes for 6.1 (2026-11-20): API from the `position-prediction` branch (the only one serving `/positions` yet) on a copy of `data/`, dashboard via `npm --prefix frontend run dev`, driven by headless Chromium (Playwright) with `fetch` wrapped to record each request's `lap` next to the slider value at call time.

- Focus a non-leader: HUL (P5 at lap 1) clicked; playback at 4× from lap 1, paused at lap 20; every lap 1-20 rendered.
- Podium percentages change lap to lap: HUL's podium value changed 7 times over laps 1-20 (e.g. 13% → 4% → 7% → <1%).
- Primary event changes when a newer event appears: 9 different primary events between laps 10 and 20 (first `10:pace_drop:ALO`, last `20:undercut_window:ALO-DOO`).
- Focus panel follows the driver: the panel showed HUL on every lap.
- No future requests: 125 lap-scoped API requests, highest `lap` 20, none above the slider value; no console errors.
- Screenshot saved to `docs/screenshot.png` (lap 20, HUL focused).
- `npm --prefix frontend run test` → 11 files, 73 tests passed; `npm --prefix frontend run build` → succeeds, no TypeScript errors (Vite warns that the Recharts chunk exceeds 500 kB).
- Re-run after merging `main` (position-prediction archived, `7187c27`) and the verify/review fixes: API from this branch's merged `backend/` on a fresh copy of `data/`; same results (HUL, laps 1-20 at 4×, podium changed 7 times, 9 primary events, focus panel on HUL every lap, 125 lap-scoped requests with none above the slider, no console errors); `npm --prefix frontend run test` → 11 files, 77 tests passed; build succeeds; screenshot refreshed.
- Backend values worth a look by `position-prediction` (displayed as served; still present on `main`'s stored positions): `/positions?lap=13` gives HUL (P7, pits on lap 14) `p_win` 0.828 and `p_podium` 1.0, back to 0 at lap 14; at lap 20 LEC (P4, +21.4 s) has `p_win` 0.85 while leader NOR has 0.14.
