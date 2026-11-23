# commentary-chart-links Specification

## Purpose

Make every number that AUGUR's event analysis and commentary quote from an event's evidence clickable, opening a small chart of that value at the event's lap, so a viewer can check a claim without searching the board.

## Requirements

### Requirement: Number links in events

`GET /api/races/{race_id}/events?lap=N` SHALL add to every event `links` = `{what, why, next, commentary}`, each a list of `{start, end, field, chart, drivers}` in text order for the event's `analysis.what`, `analysis.why`, `analysis.next`, and `commentary` (an empty list when `commentary` is null). `start` and `end` SHALL index Unicode code points of the text, `end` exclusive, covering the number and a directly following `%`. Numbers SHALL be found and compared with the grounding check's rules (shown precision, absolute values, a percentage matching a fraction 0..1). A number matching the event lap SHALL get no link; otherwise the first field of the design.md field table, in table order, whose evidence value matches SHALL give `field` (dotted for nested fields), `chart`, and `drivers`; a number matching no field SHALL get no link. All other `/events` fields SHALL stay unchanged, and links SHALL be computed from the served event only, so altering laps after N SHALL NOT change them.

#### Scenario: Gap and tyre age links

##### Example: undercut at lap 20

- **GIVEN** an `undercut_window` event at lap 20 with drivers NOR, PIA and evidence `chaser` NOR, `ahead` PIA, `gap_s` 1.84, `ahead_tyre_life` 14, `strategy` {`pit_lap` 22, `win_probability` 0.62}, `what` "NOR is 1.8 s behind PIA on lap 20.", and commentary "PIA's tyres are 14 laps old, and NOR wins 62% of runs"
- **WHEN** the client calls `events?lap=20`
- **THEN** `links.what` is [{start 7, end 10, field "gap_s", chart "trace", drivers ["NOR", "PIA"]}] and `links.commentary` is [{start 16, end 18, field "ahead_tyre_life", chart "stints", drivers ["PIA"]}, {start 42, end 45, field "strategy.win_probability", chart "pitwindow", drivers ["NOR"]}]

#### Scenario: Event lap is not linked

- **WHEN** an event at lap 20 has `tyre_life` 20 and its text says "20-lap-old"
- **THEN** that number has no link

#### Scenario: Code-point offsets in Chinese commentary

- **WHEN** the commentary is "NOR 落後 PIA 1.8 秒" and `gap_s` is 1.84
- **THEN** its link has `start` 11 and `end` 14

#### Scenario: No future laps

- **WHEN** rows with lap greater than 20 are altered and `events?lap=20` is requested again
- **THEN** every event's `links` are identical

---
### Requirement: Clickable numbers with a chart popover

The intelligence panel SHALL render each linked number in the shown analysis text and commentary quote as a button with the accessible name "<number>: show on chart". Clicking it SHALL open a popover titled "<chart title> · <drivers joined by space> · lap <event lap>" showing one chart at the event's lap E: `degradation` the link driver's points from `degradation?lap=E`; `laptimes` the lap-time chart focused on the driver from `laps?lap=E`; `trace` the link drivers' lines from `trace?lap=E`; `stints` the link drivers' rows from `stints?lap=E`; `pitwindow` `pit-window?lap=E&driver=D`; `positions` the driver's position fan from `positions/history?lap=E`. The popover SHALL show "Loading..." until the response arrives and "Could not load chart" on failure. It SHALL close on Escape, on a click outside it, or on a second click on the same number, and clicking another number SHALL replace it. The board SHALL NOT change.

#### Scenario: Open a gap popover

- **WHEN** at replay lap 25 the viewer clicks "1.8" in the what text of the lap 20 undercut event of NOR on PIA
- **THEN** a popover titled "Race trace · NOR PIA · lap 20" opens, one `trace?lap=20` request is sent, and the chart shows only NOR and PIA

#### Scenario: Close the popover

- **WHEN** the popover is open and the viewer presses Escape
- **THEN** the popover closes, and clicking the same number twice opens and then closes it

#### Scenario: Plain text without links

- **WHEN** an event's `links.why` is empty
- **THEN** the why text renders as plain text with no buttons
