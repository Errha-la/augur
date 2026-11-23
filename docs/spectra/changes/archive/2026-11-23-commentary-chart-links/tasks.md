## 1. Backend: links in /events

- [x] 1.1 Implement "Number matching shared with the grounding check": expose the number regex and the shown-precision comparison (with the percent-to-fraction rule) as public names in `augur.narration.grounding` and make `check_grounding` use them, with its behaviour unchanged. Verify that the existing `backend/tests/test_grounding.py` passes without edits.
- [x] 1.2 Implement "Links computed when serving /events", the "Field table", and "Character offsets in code points" for the "Number links in events" requirement: `augur.events.links.event_links(event)` returning `{what, why, next, commentary}` lists of `{start, end, field, chart, drivers}`. Verify with the "Gap and tyre age links" example, the "Event lap is not linked" and "Code-point offsets in Chinese commentary" scenarios, and one test per field-table row in a new `backend/tests/test_links.py`. [after: 1.1]
- [x] 1.3 Add `links` to every event served by `/api/races/{race_id}/events`, all other fields unchanged. Verify in `backend/tests/test_events_api.py` that every event has `links` with the four keys and that `commentary` links are empty when commentary is null, plus the "No future laps" scenario as a leakage test; the full backend suite passes. [after: 1.2]

## 2. Frontend: clickable numbers and popover

- [x] 2.1 Type `RaceEvent.links` in `frontend/src/api/types.ts` and build `LinkedText` (part of "Linked text and chart popover in the intelligence panel"): text split with `Array.from`, each link a button named "<number>: show on chart", text without links rendered plain. Verify with the "Plain text without links" scenario and a Chinese-offset render case in a new `frontend/src/components/links/LinkedText.test.tsx`. [after: 1.3]
- [x] 2.2 Build `ChartPopover` for the "Clickable numbers with a chart popover" requirement: title "<chart title> · <drivers> · lap <E>", one chart per kind at the event lap from the endpoints in the design (reusing the strategy chart views and `LapChart`), "Loading..." and "Could not load chart", closing on Escape and on a click outside. Verify in a new `frontend/src/components/links/ChartPopover.test.tsx` that each of the six chart kinds requests its endpoint at lap E (not the replay lap) and filters to the link's drivers, plus the loading, failure, and Escape cases. [after: 2.1]
- [x] 2.3 Render the primary event's what/why/next and commentary quote and the earlier events' analysis text through `LinkedText` in `IntelligencePanel`, with one open popover at a time and a second click closing it, board unchanged. Verify with the "Open a gap popover" and "Close the popover" scenarios in `frontend/src/components/IntelligencePanel.test.tsx` (fake backend events carrying links); the full frontend suite and `npm --prefix frontend run build` pass. [after: 2.2]

## 3. Real backend check and handoff

- [x] 3.1 Run the backend and frontend from this worktree on Abu Dhabi 2024 and, for one event of each type (degradation_warning, undercut_window, overcut_window, position_change, pace_drop), record here its linked numbers per text and what the popover shows; count linked and unlinked numbers over all 116 events' texts and record the unlinked ones that come only from template text. Write README notes for `portfolio-release` under this task. Verify that every opened popover shows the event's drivers at the event's lap and the backend and frontend suites pass. [after: 2.3]

### 3.1 results (2026-11-23, Abu Dhabi 2024, model lightgbm, commentary glm/en)

Backend (uvicorn from this worktree, main `data/`) and Vite dev server from this worktree; Playwright clicked every linked number of one event per type (38 popovers). Every popover requested its chart at the event's lap (never the replay lap) and showed only the event's drivers; 0 "Could not load chart". Backend 495 passed / 1 skipped; frontend 285 passed; `npm run build` ok.

`/events?lap=58` serves 118 events (not 116: events were re-analyzed after position-sim-calibration), 116 with commentary.

| Event (replay lap) | Text: linked numbers -> field / chart / drivers | Popover shows |
|---|---|---|
| pace_drop L10 ALO (primary) | what: 91.708 lap_time_s, 1.4 slower_s, 90.295 predicted_s -> laptimes ALO; why: 11 tyre_life -> stints ALO; next: none; commentary: same four | "Lap times · ALO · lap 10": LEC/ALO/VER lap-time lines at lap 10; "Tyre stints · ALO · lap 10": ALO row only |
| degradation_warning L11 HAM (primary) | what: 0.213 deg_s_per_lap, 8 deg_laps -> degradation HAM, 1 stint -> stints HAM; why: 0.213; next: 19 strategy.pit_lap, 93% strategy.win_probability -> pitwindow HAM; commentary: 1, 0.213, 8, 19 (11 = event lap, unlinked) | "Degradation · HAM · lap 11": 8 HAM points, HARD +0.213 s/lap (8), caption deg_s_per_lap 0.2126; "Pit window · HAM · lap 11": Best lap 21; stints HAM row |
| undercut_window L16 STR on PIA (primary) | what: 0.8 gap_s -> trace STR PIA; why: 12 ahead_tyre_life -> stints PIA, 0.125 ahead_deg_s_per_lap -> degradation PIA; next: 90% -> pitwindow STR; commentary: 0.842, 12, 0.125 | "Race trace · STR PIA · lap 16": 2 lines; stints PIA row; degradation 11 PIA points HARD +0.125; pit window STR (no further stop best) |
| overcut_window L29 HAM on VER (history row at replay lap 36; this event has no commentary) | what "VER pitted on lap 29 with HAM 2.9 s behind on lap 28.": 2.9 gap_s -> trace HAM VER, 28 tyre_life -> stints HAM (coincidence: "lap 28" is lap - 1, HAM's tyres are also 28 laps old); why: 0.028 deg_s_per_lap -> degradation HAM; next: 37 strategy.pit_lap, 88% -> pitwindow HAM | "Race trace · HAM VER · lap 29": 2 lines; stints HAM row; degradation 26 HAM points +0.028; pit window HAM Best lap 43 |
| position_change L25 DOO (primary) | what: 18 from_position, 16 to_position -> positions DOO; next: 33 laps_remaining, 16 to_position; commentary: 18, 16, 33, 16 | "Position fan · DOO · lap 25": DOO expected position with P10-P90 band |

Counts over all 118 events' what/why/next/commentary: 936 numbers linked, 297 unlinked:

- 242 are the event lap (by design; e.g. "on lap 58").
- 8 template numbers with no evidence field: the cliff threshold "more than 0.8 s slower" (7, degradation what) and the overcut's lap - 1 (1, "on lap 33").
- 6 commentary numbers grounded only by template text: the cliff threshold 0.8 repeated in commentary.
- 41 commentary numbers match no evidence at all (22 degradation, 19 undercut, e.g. "83%", "77%", "pitting on lap 39"). Cause: cached commentary is stale. 27 of 116 served commentaries now fail `check_grounding` against the current evidence, because events were re-analyzed (strategy evidence changed) after `augur.narrate` ran, and the commentary cache key does not include the evidence. Out of scope here (no change to `augur.narrate`); fix by re-running narrate for Abu Dhabi.

Other observations (not changed here):

- First-field-wins can link a number that only coincides with an evidence value (the risk the design accepts): the overcut's "on lap 28" (lap - 1) links to `tyre_life` 28. It opens a correct stints chart for HAM, but the number is a lap, not a tyre age.

- A pit-lap link opens today's `/pit-window?lap=E` (1000 runs, seed 42), whose best lap can differ from the event's stored `strategy.pit_lap` (HAM L11: event says lap 19 at 93%, popover best lap 21; HAM L29: 37 vs 43). The event strategy is the analyze-time simulation.
- Lap-time popovers use `/state` and `/laps`, which are not in the shared request cache, so reopening one re-requests them (other charts are cached).

### README notes for portfolio-release

- Numbers in event analysis and AUGUR commentary are clickable when they come from the event's evidence (gap, tyre age, degradation, lap times, pit lap and win share, positions). Clicking one opens a small chart of that value at the event's lap (race trace, tyre stints, degradation, lap times, pit window, or position fan) for the event's drivers; Escape, a click outside, or a second click closes it.
- The backend computes the links in `/events` (`links.what/why/next/commentary`, code-point offsets) with the same number rules as the commentary grounding check, so a number is linked exactly when it traces to an evidence field. The event lap and template constants (cliff threshold) stay plain text.
- Popovers never read laps after the event: links come from the served event, and every chart is requested at the event's lap.
