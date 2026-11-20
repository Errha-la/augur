## Context

The backend serves everything at lap N through `/api/races/{race_id}/{state|laps|predictions|events|strategy|positions|positions/history}?lap=N`, all cutoff-safe; `/state` includes `track_status` and each driver's `team_color`. The dashboard only has to fetch and display. It runs locally with `npm --prefix frontend run dev` next to uvicorn on port 8000. The user chose the look of the open-source project BENNNZO/f1-dashboard (Next.js + Tailwind 4 + motion) as the visual reference; AUGUR reuses its palette and layout ideas, not its code.

## Design Source

- Source: GitHub repository BENNNZO/f1-dashboard, files `src/styles/theme.css`, `src/app/layout.tsx`, `src/components/Dashboard.tsx`, `src/components/drivers/DriverRow.tsx`, `src/components/drivers/TireData.tsx`, `src/components/status-bar/TrackStatus.tsx`, read on 2026-11-19 through the GitHub API. No `.dc.html` exists, so nothing is cached under `.spectra/design-cache/`.

| Token | Value |
|---|---|
| page background | Tailwind `zinc-950` |
| card background | `#101013` |
| border | Tailwind `zinc-800` |
| muted text / subtle text / empty value | `zinc-400` / `zinc-500` / `zinc-700` |
| fastest lap / personal best | `purple-400` / `emerald-400` |
| tyre SOFT / MEDIUM / HARD / INTER / WET / unknown | `#f12f32` / `#fbcc1c` / `zinc-300` / `#128330` / `#1f6da1` / `zinc-600` |
| track status 1 / 2, 4, 6, 7 / 5 | `emerald-500` / `#fbcc1c` (7 pulses) / `#f12f32` |
| font | JetBrains Mono, weights 300-700 |
| driver row | 6 px team-colour stripe at left, position zero-padded (`01`) in muted bold 2xl, three-letter code bold 2xl, tyre letter 2xl in compound colour with tyre age in `zinc-600` after a 1 px divider |
| missing value | a short dash icon in `zinc-800` |
| motion (change `polish`) | rows animate to new positions, ease `cubic-bezier(0.2, 1, 0.2, 1)`, 0.75 s |

## Goals / Non-Goals

**Goals:**

- One screen that shows the race state, the most important analysis, and one followed driver at the selected lap.
- Smooth playback without stale data flashing from an earlier lap.
- Nothing on screen depends on data after the selected lap.

**Non-Goals:**

- Mobile layout below 1024 px width (the page stays usable but is not optimized).
- Track map, 3D circuit, team radio, race control messages, mini sectors, car telemetry charts, driver photos.
- Routing, authentication, deployment, light/dark toggle.
- Backend changes.
- Race Wrapped story cards (change `race-wrapped`).
- Dashed predicted-lap lines in the chart and row slide animation (change `polish`, Stage 3).
- LLM commentary display (change `llm-commentary`).

## Decisions

### Timing-screen layout after BENNNZO/f1-dashboard

Grid of a full-height page: status bar on top (race selector, replay controls, lap count `LAP n/total`, track status pill); below it a left column with the timing list and a right area split into the intelligence panel (top) and a bottom row holding the focus-driver panel and the chart, with the event timeline under them. Cards use the tokens in the Design Source table. Alternative: multi-page tabs. Rejected because the point is seeing state and analysis together.

### Fetch everything per lap with request cancellation

On every lap change the app fetches `state`, `laps`, `predictions`, `events`, and `positions` for that lap in parallel, aborting any in-flight requests for the previous lap with `AbortController`, and renders only when all five for the current lap have arrived. Alternative: fetch the whole race once and slice in the browser. Rejected because it would put future laps in the browser and break the no-leakage rule.

### Newest highest-severity event is primary

The primary event is the first event of the `/events` response (lap descending, then severity descending). When the lap changes and a different event becomes first, it replaces the primary and the previous primary moves into history. Clicking a history item expands it in place; it does not replace the primary.

### One focus driver drives the detail views

The focus driver defaults to the driver in position 1 at lap 1 and changes when a timing row is clicked. On race change it is kept if that code exists in the new race, otherwise reset to position 1. The focus driver's row, timeline markers, and events are highlighted with its team colour. The live strategy table in the focus panel requests `/strategy` for the current lap only when playback is paused, or during playback on laps divisible by 5, so playback is not slowed by simulations.

### Chart compares the focus driver with neighbours

Recharts `LineChart` with solid lines for actual lap times for the focus driver and the cars directly ahead and behind at the current lap (one or two neighbours at the ends of the order). Lines use the team colours. Non-clean laps (null lap time) leave gaps. Alternative: manual multi-select. Rejected because clicking a row already selects the focus driver, and neighbours are the comparison that matters for undercuts.

Lines are told apart by more than colour, because teammates share a team colour. The focus driver's line is 3 px at full opacity; each neighbour line is 1.5 px at 75% opacity; the legend names every line by driver code. When a neighbour is the focus driver's teammate, that neighbour's line also shows a dot at every plotted lap. Dash patterns are not used here, because change `polish` reserves dashed lines for predicted lap times. Alternative: a second colour per team. Rejected because team colours are the dashboard's identity code and a substitute colour would not match the timing rows.

Neighbours are chosen at the current lap N and plotted with their full history up to lap N, so after an overtake the plotted neighbours change. The legend title reads `Neighbours at lap N` (with the current N) so that this change has a visible reason. Alternative: keep the neighbours of an earlier lap. Rejected because the chart exists to compare the cars that matter now.

### Position probabilities in the timing list and focus panel

Position prediction is AUGUR's headline output, so it sits next to the timing data rather than in a separate view. Each timing row shows `WIN` and `PODIUM` as whole percentages (`<1%` below 0.5%, dash when null) with a thin bar under the podium value. The focus panel shows expected position with its p10-p90 range, the three probabilities, and a small chart of `p_win` and `p_podium` over laps 1 to N from `/positions/history?lap=N`, refreshed on the same schedule as the strategy table. A note "Assumes a green race to the end" sits under the focus panel probabilities.

### Vite proxy for the API

`vite.config.ts` proxies `/api` to `http://localhost:8000`, so the client uses relative URLs. Alternative: absolute URL with CORS. Rejected to keep one config point.

### Component tests with mocked fetch

Vitest + Testing Library with `fetch` mocked by fixture JSON shaped like the backend responses. A final manual check runs both servers on the demo races.

## Implementation Contract

**Behavior**

- On load the app calls `/api/races`, selects the first race, sets lap 1, and shows its data.
- Replay controls: slider 1..total_laps; previous / next buttons; Left / Right arrow keys step one lap; Space toggles play; playback advances one lap per 1000 ms at 1×, 500 ms at 2×, 250 ms at 4×, waits for the current lap to render before the next tick, and stops at `total_laps`.
- Timing row fields: team stripe, position (`01`), code, tyre letter (S/M/H/I/W, or dash) with tyre age, gap to leader (`+x.xxx`, `LEADER`, or `+n LAP`), last lap time (`m:ss.sss`, purple when it is the fastest clean lap of the race so far, green when it is the driver's best so far), predicted next lap time, `deg_s_per_lap` (`+0.000/lap`), a "CLIFF" tag when `cliff` is true, `WIN` and `PODIUM` percentages. Null values show the dash icon.
- Focus panel: driver code and team, stint bar (one segment per stint, coloured by compound, width proportional to laps, up to the current lap), `deg_s_per_lap` and cliff, predicted next lap, expected position with p10-p90, win/podium/points probabilities with their history chart, strategy table (strategy, mean, p10-p90, win probability) with "Simulating..." while loading, and the list of events involving the driver.
- Intelligence panel: primary card shows type label, lap, drivers, severity bar (0-100), title, What / Why / Next paragraphs, and evidence; for `degradation_warning` and `undercut_window` it also shows the strategy table for the event's first driver at the event lap. Event history lists every other event at lap ≤ current lap as one collapsed row (lap, type, title). Event timeline marks each event at lap ≤ current lap; clicking sets the lap.

**Failure modes**

- Backend unreachable: banner "Backend not reachable at /api. Start it with: uvicorn augur.api:app" and a Retry button.
- No races: message "No races ingested. Run: python -m augur.ingest --year 2024 --rounds 1 24".
- `analyzed` false: intelligence panel shows "Race not analyzed. Run: python -m augur.analyze --race <race_id>" while the timing list, focus panel, and chart still work.

**Acceptance**

- `npm --prefix frontend run test` passes; `npm --prefix frontend run build` succeeds with no TypeScript errors.
- Manual: with backend running, play `2024-24-abu-dhabi-grand-prix` from lap 1 to 20 at 4× with a non-leader focused; confirm podium percentages change from lap to lap, the primary event changes when a newer event appears, the focus panel follows the chosen driver, and the network log shows no request with a lap above the slider value.

**Scope**

- In: everything under `frontend/` for the four capabilities, README run instructions.
- Out: backend code, new endpoints, Wrapped, deployment.

## Risks / Trade-offs

- [Five requests per lap at 4× playback may lag on slow machines] → request cancellation keeps only the latest lap; playback waits for the current lap to render before scheduling the next tick.
- [Strategy simulation takes noticeable time] → focus-panel strategy refreshes only when paused or every 5 laps; "Simulating..." placeholder keeps the rest of the panel responsive.
- [Copying a reference design too closely] → AUGUR reuses colour tokens and layout ideas only; no source files are copied.
