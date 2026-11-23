## Context

Every event in `/events` has template analysis (`what`, `why`, `next`, built in `augur.events.analysis` from the event's `evidence`) and, when `augur.narrate` cached one, LLM `commentary`. `augur.narration.grounding.check_grounding` keeps commentary only when every number in it matches the event lap, an evidence value, or a number in the template text at the shown precision (a percentage matches a fraction 0..1). The strategy chart views (`RaceTraceView`, `StintsView`, `DegradationView`, `PitWindowView`, `PositionFanView`) and `LapChart` render from plain responses. The intelligence panel (`frontend/src/components/IntelligencePanel.tsx`) shows the primary event's analysis and commentary quote and the earlier events.

The user chose (2026-11-23): clicking a number opens a popover with a small chart (the board does not change); numbers in both the template analysis and the commentary are clickable; the backend computes the links when serving `/events`.

This is Wave 3 of Stage 4 (`AGENTS.md`): backend and frontend in one worktree, runs alone.

## Goals / Non-Goals

**Goals:**

- `/events` tells the frontend which numbers in each text come from which evidence field, which chart shows it, and for which drivers.
- Clicking such a number shows that value on a small chart at the event's lap.
- No lap after the replay lap is read: links come from the event only, and popover charts request the event's lap, which is never after the replay lap.

**Non-Goals:**

- No links in `outcome_text` or titles.
- No driver-code links; only numbers.
- No board change on click (no flash, no added widget): rejected by the user in favour of a popover.
- No stored links and no change to `augur.narrate` or the commentary table.
- No new endpoint and no new chart type; popovers reuse existing endpoints and chart views.
- No README edit; notes go to tasks.md for `portfolio-release`.

## Decisions

### Links computed when serving /events

`augur.events.links.event_links(event) -> {"what": [...], "why": [...], "next": [...], "commentary": [...]}` is a pure function of one served event (its `lap`, `drivers`, `evidence`, `analysis`, `commentary`). The `/events` route calls it for every event after attaching commentary. Reason: the user's choice; the template text and cached commentary get links without re-running `augur.narrate` or a migration. Alternative: store links at narrate time. Rejected by the user (needs a column and a re-run, and template text would still need serving-time links).

### Number matching shared with the grounding check

The number regex (`_NUMBER_RE`) and the precision rule (`_matches`, including percent-to-fraction for values in 0..1) move to public names in `augur.narration.grounding` (`NUMBER_RE`, `matches_shown`) and both modules use them; `check_grounding` behaviour is unchanged (its tests stay as they are). For each number in a text, in order: if it matches the event lap, it gets no link; otherwise the first field in the field table, in table order, whose evidence value matches it gives the link; a number matching no field gets no link. Values are compared as absolute values, as in grounding. Reason: a number is linked exactly when grounding would trace it to evidence, so links never point at a value the event does not hold. Alternative: a separate frontend matcher. Rejected by the user (two copies of the rules).

### Field table

| Evidence field | Chart kind | Drivers |
|---|---|---|
| `deg_s_per_lap`, `deg_laps` | `degradation` | `driver` |
| `ahead_deg_s_per_lap` | `degradation` | `ahead` |
| `lap_time_s`, `predicted_s`, `slower_s` | `laptimes` | `driver` |
| `gap_s` | `trace` | `chaser` or `driver`, then `ahead` |
| `tyre_life`, `stint` | `stints` | `driver` |
| `ahead_tyre_life`, `ahead_stint` | `stints` | `ahead` |
| `chaser_tyre_life` | `stints` | `chaser` |
| `strategy.pit_lap`, `strategy.win_probability` | `pitwindow` | the event's first driver |
| `from_position`, `to_position`, `places`, `laps_remaining` | `positions` | `driver` |

A field absent from the evidence or null is skipped. Drivers missing from the evidence are left out of the list. The event lap rule comes first, so a tyre age equal to the event lap is not linked (accepted: the number then reads as the lap).

### Character offsets in code points

Each link is `{start, end, field, chart, drivers}` where `start`/`end` index Unicode code points of the text (Python `str` indexes), `end` exclusive, covering the digits and a directly following `%`. The frontend splits text with `Array.from` so code-point offsets hold for Chinese commentary too. Alternative: UTF-16 offsets. Rejected because Python strings index code points and the backend would need conversion.

### Linked text and chart popover in the intelligence panel

`LinkedText` renders a text with its links as `<button>` spans (dotted underline, `aria-haspopup="dialog"`, accessible name "<number>: show on chart"). Clicking opens `ChartPopover`, a small dialog (about 320×200 px) anchored under the number, titled "<chart title> · <drivers> · lap <event lap>", that shows one chart at the event's lap:

- `degradation`: `/degradation?lap=E`, only the points of the link's driver, fit line recomputed from them, caption with the evidence value.
- `laptimes`: `LapChart` with `/laps?lap=E` and the state drivers at E, focused on the link's driver.
- `trace`: `/trace?lap=E`, only the link's drivers.
- `stints`: `/stints?lap=E`, only the link's drivers' rows.
- `pitwindow`: `/pit-window?lap=E&driver=D`.
- `positions`: `/positions/history?lap=E`, fan for the link's driver.

Requests go through the shared request cache. The popover closes on Escape, on a click outside, or on a second click on the same number; opening another number replaces it. Reason: the user's choice of a popover; reusing the chart views keeps one rendering per chart. Alternative: highlight a board widget. Rejected by the user.

## Implementation Contract

**Backend**: `/api/races/{race_id}/events` adds to each event `"links": {"what": [Link], "why": [Link], "next": [Link], "commentary": [Link]}` with `Link = {"start": int, "end": int, "field": str, "chart": "degradation"|"laptimes"|"trace"|"stints"|"pitwindow"|"positions", "drivers": [str]}`, links in text order; `commentary` is `[]` when `commentary` is null. All other `/events` fields are unchanged. Nested fields use dotted names (`strategy.pit_lap`).

**Frontend**: `RaceEvent.links` typed as above. In the intelligence panel, the primary event's `what`, `why`, `next` and commentary quote render through `LinkedText`; earlier events' visible analysis text does too. Popover states: "Loading..." before the response, "Could not load chart" on failure, the chart otherwise.

**Acceptance**: tests named in tasks.md pass (pytest and Vitest); a leakage test shows `/events?lap=N` links unchanged when laps after N are altered; the final task checks links and popovers against the real backend on Abu Dhabi 2024 and records each event type's linked numbers in tasks.md.

**Scope**: In: `augur.events.links`, the shared number rules in `augur.narration.grounding`, the `/events` route, `frontend/src/api/types.ts`, `frontend/src/components/IntelligencePanel.tsx`, new `frontend/src/components/links/`, tests. Out: `augur.narrate`, stored tables, board and widgets, README.

## Risks / Trade-offs

- [A number matches two fields, e.g. a tyre age equal to a stint length] → The first field in table order wins; the popover still shows a chart for that driver and lap.
- [Commentary paraphrases a number at another precision] → Matching uses the shown precision like grounding. A grounded number that matches only the template text (for example the overcut's lap − 1, or the cliff threshold) has no evidence field and stays plain text.
- [Popover charts are small] → Each shows only the link's drivers; the full chart stays available as a board widget.
