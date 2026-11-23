## Purpose

Board widgets that draw AUGUR's strategy charts (race trace, pit-stop clock, pit window, tyre stints, degradation, pace comparison, position fan, and position heatmap) at the current replay lap from the `strategy-charts-api` endpoints, so a viewer can read a race the way a strategy team does.

## ADDED Requirements

### Requirement: Chart widget loading, errors, and request schedule

Every chart widget SHALL request its endpoint for replay lap N and show "Loading..." until the first response arrives. A failed request SHALL show "Could not load <widget title>" and SHALL NOT stop later requests. `pitwindow` and `fan` widgets SHALL request when playback is paused and during playback only on laps divisible by 5, keeping the last response on screen in between; every other chart widget SHALL request at every lap. Identical requests from several widgets at the same lap SHALL be sent once.

#### Scenario: Pit window during playback

- **WHEN** playback runs from lap 11 to lap 16 with one `pitwindow` widget following NOR
- **THEN** exactly one `pit-window` request is sent, for lap 15

#### Scenario: Stints every lap

- **WHEN** playback runs from lap 11 to lap 13 with one `stints` widget
- **THEN** `stints` requests are sent for laps 12 and 13

#### Scenario: Failed request

- **WHEN** the `trace` request for lap 20 fails with HTTP 500
- **THEN** the widget shows "Could not load Race trace", and at lap 21 it sends a new request

---
### Requirement: Race trace widget

A `trace` widget SHALL plot one line per driver of the `trace` response, lap on the x axis and `delta_s` on the y axis with positive values above zero, in team colours, the focus driver's line drawn thicker than the others, and the caption "Reference pace <reference_lap_s as a lap time>". When `reference_lap_s` is null it SHALL show "No laps yet".

#### Scenario: Reference pace caption

##### Example: Abu Dhabi lap 58

- **GIVEN** the `trace` response has `reference_lap_s` 90.993
- **WHEN** the widget renders
- **THEN** the caption reads "Reference pace 1:30.993"

#### Scenario: No laps yet

- **WHEN** the `trace` response has `reference_lap_s` null
- **THEN** the widget shows "No laps yet"

---
### Requirement: Pit clock widget

A `pitclock` widget SHALL draw a circle whose full turn equals `lap_length_s`, with the leader at the top and each car of `cars` placed clockwise at `(gap_to_leader_s mod lap_length_s) / lap_length_s` of a turn as a dot in its team colour with its code, cars one or more laps down labelled "+<laps_behind_leader>L", and the widget's driver ringed. It SHALL mark the rejoin gap and show "Pit now: rejoin P<position>, <ahead_gap_s> s behind <ahead>, <behind_gap_s> s ahead of <behind>" (omitting the part for a null car), "Pit loss <pit_loss_s> s", and the caption "Snapshot: assumes no other car pits this lap". When `rejoin` is null it SHALL show "<code> has no gap yet".

#### Scenario: Rejoin text

##### Example: rejoin between two cars

- **GIVEN** the `rejoin` response for driver NOR has `rejoin` {position 7, ahead RUS, ahead_gap_s 1.1, behind HAM, behind_gap_s 0.6} and `pit_loss_s` 21.5
- **WHEN** the widget renders
- **THEN** it shows "Pit now: rejoin P7, 1.1 s behind RUS, 0.6 s ahead of HAM" and "Pit loss 21.5 s"

#### Scenario: Leader rejoins in front

- **WHEN** `rejoin` has position 1, `ahead` null, `behind` SAI with `behind_gap_s` 2.0
- **THEN** it shows "Pit now: rejoin P1, 2.0 s ahead of SAI"

#### Scenario: Car positions on the clock

##### Example: quarter and wrapped gaps

| lap_length_s | gap_to_leader_s | laps_behind_leader | Angle | Label |
|---|---|---|---|---|
| 88.0 | 0.0 | 0 | 0° | code only |
| 88.0 | 22.0 | 0 | 90° | code only |
| 88.0 | 110.0 | 1 | 90° | code and "+1L" |

---
### Requirement: Pit window widget

A `pitwindow` widget SHALL plot `delta_s` against `pit_lap` for every plan with a pit lap, with a p10-p90 band, mark `best_pit_lap` with "Best: lap <best_pit_lap>", draw the no-stop plan (pit_lap null) as a dashed horizontal line at its `delta_s` labelled "No further stop", and show the caption "Green race assumed". With empty `plans` it SHALL show "No pit window left" when N is at least total_laps − 2, otherwise "Not enough laps yet".

#### Scenario: Best lap and no-stop line

- **WHEN** the response has plans for laps 21 to 56 and a no-stop plan, with `best_pit_lap` 32
- **THEN** the chart shows "Best: lap 32" and a dashed line labelled "No further stop"

#### Scenario: Empty window messages

##### Example: Abu Dhabi, 58 laps

| Lap N | plans | Message |
|---|---|---|
| 2 | empty | Not enough laps yet |
| 56 | empty | No pit window left |
| 58 | empty | No pit window left |

---
### Requirement: Tyre stints widget

A `stints` widget SHALL show one row per driver in the response order, each stint as a segment from `start_lap` to `end_lap` on an axis from lap 1 to the race's total laps, coloured by compound, with the compound letter inside segments at least 4 laps long, and the focus driver's row highlighted. When every driver has no stints it SHALL show "No laps yet".

#### Scenario: Running stint ends at the current lap

- **WHEN** at lap 30 NOR's stints are MEDIUM laps 1-25 and HARD laps 26-30
- **THEN** NOR's row has a MEDIUM segment covering laps 1-25 and a HARD segment covering laps 26-30, and laps 31 onwards are empty

---
### Requirement: Degradation widget

A `degradation` widget SHALL plot each compound's points as `tyre_age` against `fuel_corrected_s` in the compound's colour, draw the `fit` line for compounds with a fit, show a legend entry "<compound> +<slope_s_per_lap> s/lap (<n>)" for compounds with a fit and "<compound> (<point count>)" otherwise, and draw the focus driver's points larger. With no compounds it SHALL show "No laps yet".

#### Scenario: Legend entries

##### Example: fit and no fit

- **GIVEN** SOFT has fit {slope_s_per_lap 0.179, n 24} and HARD has 3 points and fit null
- **WHEN** the widget renders
- **THEN** the legend shows "SOFT +0.179 s/lap (24)" and "HARD (3)"

---
### Requirement: Pace comparison widget

A `pace` widget SHALL plot `fuel_corrected_s` by lap for its drivers from the `degradation` points, one line per driver in team colours with gaps on laps without a point, and the caption "Fuel-corrected clean laps". Its `drivers` setting SHALL be absent or empty (follow the focus driver and the cars directly ahead and behind at lap N) or one to four driver codes chosen in a title-bar picker that offers "Follow focus" and toggles each driver of the race, refusing a fifth pick. Pinned codes not in the race SHALL be listed as "<codes> not in this race" and skipped; when none remain the widget SHALL follow the focus driver. When the drivers have no points it SHALL show "No clean laps for <codes> yet".

#### Scenario: Follow focus

- **WHEN** the setting is empty, the focus driver is LEC, and at lap 20 the order is NOR, LEC, PIA
- **THEN** the widget plots NOR, LEC, and PIA

#### Scenario: Four drivers at most

- **WHEN** the setting holds VER, NOR, LEC, PIA and the viewer toggles HAM
- **THEN** the setting is unchanged

#### Scenario: Pinned driver missing

- **WHEN** the setting holds SAR and NOR for a race without SAR
- **THEN** the widget shows "SAR not in this race" and plots NOR

---
### Requirement: Position fan widget

A `fan` widget SHALL plot, for its driver, `expected_position` by lap from `positions/history?lap=N` with a band from `position_p10` to `position_p90`, position 1 at the top of the y axis, in the driver's team colour. When `analyzed` is false it SHALL show "Race not analyzed".

#### Scenario: Band follows the history

- **WHEN** at lap 3 the history for NOR has expected positions 2.0, 1.8, 1.5 with p10 1 and p90 3 on every lap
- **THEN** the line passes 2.0, 1.8, 1.5 at laps 1-3 inside a band from 1 to 3

#### Scenario: Not analyzed

- **WHEN** the history response has `analyzed` false
- **THEN** the widget shows "Race not analyzed"

---
### Requirement: Position heatmap widget

A `heatmap` widget SHALL show one row per driver in the `positions/distribution` order and one column per position P1 to Pn, each cell's opacity equal to that driver's share of the position in the driver's team colour, the percentage written in cells of at least 10 % and shown on hover for every cell. When `analyzed` is false it SHALL show "Race not analyzed"; when every `position_distribution` is null it SHALL show "No distribution stored; re-run analyze". A row with a null distribution SHALL show its code and empty cells.

#### Scenario: Cell labels

##### Example: one driver

- **GIVEN** NOR's distribution is [0.61, 0.22, 0.1, 0.07]
- **WHEN** the widget renders
- **THEN** NOR's P1, P2, and P3 cells read "61%", "22%", and "10%", and the P4 cell has no text

#### Scenario: Stored before the distribution existed

- **WHEN** every driver's `position_distribution` is null
- **THEN** the widget shows "No distribution stored; re-run analyze"
