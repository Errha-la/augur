## Context

`strategy-charts-api` (archived 2026-11-23, merged to `main`) serves `trace`, `rejoin`, `pit-window`, `stints`, `degradation`, and `positions/distribution`, and adds `position_p10` / `position_p90` to `positions/history`; its design's Implementation Contract fixes the response shapes. `dashboard-canvas` (archived 2026-11-23) gives the board: a widget registry (`frontend/src/canvas/registry.ts`), widget instances with settings, a per-widget driver that follows the focus driver by default, three presets defined in code (`frontend/src/canvas/presets.ts`), and a URL-keyed shared request cache (`frontend/src/api/requestCache.ts`). Its Non-Goals deferred eight chart widgets to this change: race trace, pit clock, pit window, stints, heatmap, fan, degradation, pace. `position-sim-calibration` Non-Goals left the focus panel note "Assumes a green race to the end" for this change to correct, because the position simulator now draws safety-car and VSC periods while `strategy.simulate` still assumes a green race.

This is Wave 2 of Stage 4 (`AGENTS.md`): `frontend/` only, own worktree. `strategy-charts-api` is archived, so the widgets are built and tested against the real backend; no mocks are needed in the app (unit tests stub `fetch` as the existing tests do).

## Goals / Non-Goals

**Goals:**

- Eight widget types that render the new chart data at replay lap N and handle empty, not-analyzed, and error responses.
- Driver settings for the driver-based charts, reusing the per-widget driver rules.
- A STRATEGY preset and one new chart in each existing preset.
- Correct notes about safety cars in the focus panel.

**Non-Goals:**

- No backend change and no new endpoint. The `pace` widget reuses the `degradation` points (fuel-corrected clean laps) instead of a new pace endpoint, so it plots the same corrected times the backend computes.
- No projected future laps in any chart; projections stay in the strategy table and pit window.
- No clickable commentary numbers linked to charts: `commentary-chart-links` (Wave 3).
- No change to the grid engine, board persistence format, export/import format, or the existing widgets' content.
- No README edit; README notes go to tasks.md for `portfolio-release`.
- No new chart dependency.

## Decisions

### Eight chart widget types in the registry

The registry gains `trace`, `pitclock`, `pitwindow`, `stints`, `degradation`, `pace`, `fan`, and `heatmap`, each with a title, default size, minimum size, and settings schema (table in the Implementation Contract). `+ Widget` lists them after the existing five. The sanitizer keeps only settings the type declares, as today. Reason: the registry is the single list the board, "+ Widget", and import use, so adding types there makes them work everywhere. Alternative: one generic `chart` type with a `kind` setting. Rejected because each chart has its own size, settings, and title, which the registry already models per type.

### Driver settings for chart widgets

`pitclock`, `pitwindow`, and `fan` use the existing `driver` setting with the per-widget driver rules (follow focus by default, pinned code, "<code> is not in this race"). `pace` gets a new `drivers` setting: absent or empty follows the focus driver and the cars directly ahead and behind at lap N (the same neighbour rule as the lap chart); otherwise a list of one to four pinned codes, picked by toggling drivers in a title-bar picker that shows "Follow focus" and every driver. Pinned codes not in the race are skipped and listed as "<codes> not in this race"; if none remain the widget follows the focus driver. The sanitizer keeps at most four valid driver codes in order without duplicates. Reason: the user chose a multi-driver pace comparison (2026-11-23). Alternative: reuse the single `driver` setting and always add neighbours. Rejected because comparing two drivers who are not neighbours is the main use.

### One chart component per type with a shared data hook

Each type is a component under `frontend/src/components/charts/` that receives the race id, lap N, playing state, resolved driver(s), and team colours, and fetches through `useKeyedFetch` with the shared request cache, so two widgets with the same URL send one request. A key of null (skipped refresh) keeps the last response on screen. Recharts draws `trace`, `pitwindow`, `degradation`, `pace`, and `fan`; `stints` and `heatmap` are CSS grids; `pitclock` is an SVG circle. Reason: the existing `LapChart` uses Recharts and the grid-like charts read better as plain markup. Alternative: one Recharts chart for all. Rejected because a heatmap and a clock are awkward in Recharts.

### Request schedule per widget

`pitwindow` and `fan` follow the focus panel schedule (`refreshesAt`: when paused, and during playback only on laps divisible by 5), because `pit-window` runs the strategy simulator and `fan` shares `/positions/history` with the focus panel. All other chart widgets request at every lap. Measured on Abu Dhabi 2024 lap 58 (server side, `strategy-charts-api` task 4.1): `rejoin` 42 ms, `stints` 14 ms, `trace` 11 ms, `degradation` 10 ms, `positions/distribution` 2 ms; at 4× playback a lap lasts 250 ms (`TICK_MS`). That every-lap requests keep up at 4× with a full STRATEGY board is an estimate, checked in the final task by playing Abu Dhabi at 4× and recording whether laps advance on schedule. Alternative: every widget on the 5-lap schedule. Rejected because the pit clock and stints should move with the replay.

### Chart content

- `trace`: one line per driver, x lap 1..N, y `delta_s` (positive up = ahead of the reference pace), team colours, focus driver drawn thicker and others at reduced opacity; caption "Reference pace <reference_lap_s formatted as lap time>".
- `pitclock`: a circle whose full turn is `lap_length_s`; the leader at the top, each car at angle `(gap_to_leader_s mod lap_length_s) / lap_length_s × 360°` clockwise, as a team-coloured dot with its code; the widget's driver ringed; a hollow marker at the rejoin gap with the text "Pit now: rejoin P<position>, <ahead_gap_s> s behind <ahead>, <behind_gap_s> s ahead of <behind>" (parts for a null car omitted) and "Pit loss <pit_loss_s> s"; caption "Snapshot: assumes no other car pits this lap".
- `pitwindow`: x pit lap, y `delta_s` (seconds slower than the best plan) with a p10-p90 band shifted by the same offset; the best pit lap marked "Best: lap <best_pit_lap>"; the no-stop plan as a dashed horizontal line labelled "No further stop"; caption "Green race assumed".
- `stints`: one row per driver in running order, segments from `start_lap` to `end_lap` on a 1..total_laps axis, coloured by compound (existing `compoundColor`), letter inside wide segments; focus driver row highlighted.
- `degradation`: scatter of `tyre_age` against `fuel_corrected_s`, one colour per compound, the `fit` line per compound, legend "<compound> +<slope_s_per_lap> s/lap (n)"; the focus driver's points drawn larger.
- `pace`: lines of `fuel_corrected_s` by lap for the selected drivers from the `degradation` points (laps that are not clean leave gaps), team colours (teammates dashed for the second driver).
- `fan`: x lap 1..N, y position with P1 at the top, `expected_position` line and `position_p10`–`position_p90` band in the driver's team colour.
- `heatmap`: rows are drivers in the response order, columns P1..Pn; each cell's opacity is the share (0 transparent, 1 full) in the driver's team colour, with the percentage shown on hover and in cells of 10 % or more.

Empty and error states are listed in the Implementation Contract.

### STRATEGY preset and preset updates

**Supersedes**: dashboard-canvas / Presets and custom boards

Four built-in presets; BATTLE stays the first-visit board. New STRATEGY preset (id `strategy`): `pitwindow` follow (0,0,7,6); `pitclock` follow (7,0,5,6); `stints` (0,6,7,7); `degradation` (7,6,5,7); `trace` (0,13,12,6). Existing presets change one widget each: PIT WALL `lapchart` (5,6,7,5) becomes `pitwindow` follow at the same place; BATTLE `driver` (5,6,7,7) becomes `trace`; PACE `driver` (7,6,5,8) becomes `pace` follow. `fan` and `heatmap` are added from "+ Widget". All other preset widgets, settings, and positions stay as in `dashboard-canvas`. Stored edited presets keep the viewer's copy; unedited presets show the new definitions because presets are defined in code. Reason: user choice 2026-11-23. Alternative: only extend the existing three. Rejected by the user.

### Safety-car notes in the focus panel

The note under the position probabilities becomes "Includes random safety-car and VSC periods". The strategy table gets the note "Assumes a green race to the end" under it, since `strategy.simulate` has no safety cars (`position-sim-calibration` Non-Goals). Reason: the old single note now describes only the strategy table.

## Implementation Contract

**Widget types** (default w×h, minimum w×h, settings):

| Type | Title | Default | Minimum | Settings | Endpoint | Schedule |
|---|---|---|---|---|---|---|
| `trace` | Race trace | 12×6 | 4×4 | none | `trace?lap=N` | every lap |
| `pitclock` | Pit clock | 5×6 | 4×5 | `driver` | `rejoin?lap=N&driver=D` | every lap |
| `pitwindow` | Pit window | 7×6 | 4×4 | `driver` | `pit-window?lap=N&driver=D` | `refreshesAt` |
| `stints` | Tyre stints | 7×7 | 4×4 | none | `stints?lap=N` | every lap |
| `degradation` | Degradation | 5×7 | 4×4 | none | `degradation?lap=N` | every lap |
| `pace` | Pace compare | 7×6 | 4×4 | `drivers` | `degradation?lap=N` | every lap |
| `fan` | Position fan | 6×5 | 4×4 | `driver` | `positions/history?lap=N` | `refreshesAt` |
| `heatmap` | Position odds | 7×8 | 4×5 | none | `positions/distribution?lap=N` | every lap |

`WidgetSettings` gains `drivers?: string[]` (one to four driver codes, `pace` only). The `driver` setting rules of `dashboard-canvas` apply to `pitclock`, `pitwindow`, and `fan`.

**API client** (`frontend/src/api/client.ts`, `types.ts`): `fetchTrace(raceId, lap)`, `fetchRejoin(raceId, lap, driver)`, `fetchPitWindow(raceId, lap, driver)`, `fetchStints(raceId, lap)`, `fetchDegradation(raceId, lap)`, `fetchPositionDistribution(raceId, lap)`, each through the shared request cache with an `AbortSignal`, typed exactly as the `strategy-charts-api` Implementation Contract; `PositionsHistoryResponse` driver entries gain `position_p10` and `position_p90`.

**Empty and error states** (text shown in the widget body):

- Before the first response: "Loading...".
- A failed request: "Could not load <title>" and the widget keeps working on the next lap or key.
- `trace` with `reference_lap_s` null, `stints` or `degradation`/`pace` with no data: "No laps yet".
- `pitclock` with `rejoin` null: "<code> has no gap yet".
- `pitwindow` with empty `plans`: "No pit window left" when N ≥ total_laps − 2, else "Not enough laps yet".
- `fan` and `heatmap` with `analyzed` false: "Race not analyzed"; `heatmap` with every `position_distribution` null: "No distribution stored; re-run analyze".
- `pace` with no selected driver point: "No clean laps for <codes> yet".

**Acceptance**: Vitest tests named in tasks.md pass; `npm --prefix frontend run build` passes; the final task checks each widget against the real backend on Abu Dhabi 2024 at laps 1, 20, and 58 and records the 4× playback check in tasks.md.

**Scope**: In: `frontend/src/api/`, `frontend/src/canvas/`, `frontend/src/components/` (new `charts/` directory, FocusPanel and StrategyTable notes), `frontend/src/App.tsx`, tests. Out: `backend/`, the grid engine, persistence and file formats, README.

## Risks / Trade-offs

- [A full STRATEGY board sends about five requests per lap at 4× playback] → Measured server times are at most 42 ms per request; the final task plays Abu Dhabi at 4× and records whether laps keep advancing every 250 ms. If they lag, the every-lap widgets move to the `refreshesAt` schedule (a spec change first).
- [Pit clock wraps lapped cars onto the same circle] → Cars a lap or more down are placed by their gap modulo the lap length and labelled "+<laps_behind_leader>L".
- [Viewers with an edited preset do not see the new charts] → Intended by `dashboard-canvas`; "Reset to preset" shows the new definition.
- [Pace reads only clean laps] → Pit laps, safety-car laps, and lap 1 leave gaps; the caption says "Fuel-corrected clean laps".
