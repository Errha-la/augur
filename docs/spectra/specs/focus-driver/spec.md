# focus-driver Specification

## Purpose

Let the viewer follow one driver through the race with a dedicated panel and highlights, so AUGUR's analysis can be read from that driver's point of view.

## Requirements

### Requirement: Focus driver selection

The dashboard SHALL keep exactly one focus driver. It SHALL default to the driver in position 1 at lap 1 of the selected race, SHALL change when the viewer clicks a timing row, and on race change SHALL stay the same driver code when that driver exists in the new race, otherwise reset to position 1 at lap 1.

#### Scenario: Selection rules

- **WHEN** the race loads, a row is clicked, or the race changes
- **THEN** the focus driver follows the cases below

##### Example: focus changes

| Situation | Focus driver |
| --------- | ------------ |
| race loads, P1 at lap 1 is VER | VER |
| viewer clicks the NOR row | NOR |
| race changes, NOR is in the new race | NOR |
| race changes, the focused code is not in the new race | P1 at lap 1 of the new race |

---
### Requirement: Focus driver panel

The focus panel SHALL show the driver's code and team, a stint bar with one segment per stint up to the current lap (coloured by compound, width proportional to laps in the stint), `deg_s_per_lap` and the cliff flag, the predicted next lap, expected position with its p10-p90 range, `p_win`, `p_podium`, and `p_points`, a chart of `p_win` and `p_podium` for laps 1 to N from `/positions/history?lap=N`, the note "Assumes a green race to the end", a strategy table from `/strategy?lap=N&driver=<focus>`, and the list of events at lap N or earlier whose `drivers` include the focus driver. The strategy table and the probability history SHALL be requested when playback is paused, and during playback only on laps divisible by 5; it SHALL show "Simulating..." until the response arrives.

#### Scenario: Stint bar up to the current lap

##### Example: two stints

- **GIVEN** the focus driver ran MEDIUM on laps 1-18 and HARD from lap 19
- **WHEN** the current lap is 25
- **THEN** the stint bar has a MEDIUM segment of 18 laps and a HARD segment of 7 laps

#### Scenario: Strategy requests during playback

- **WHEN** playback runs from lap 11 to lap 16
- **THEN** a strategy request and a probability history request are made for lap 15 only

#### Scenario: Probability display

##### Example: P5 driver at lap 30

- **GIVEN** `/positions?lap=30` gives the focus driver `expected_position` 4.6, `position_p10` 3, `position_p90` 7, `p_win` 0.04, `p_podium` 0.31, `p_points` 0.99
- **WHEN** the focus panel renders
- **THEN** it shows `P4.6 (P3-P7)`, `WIN 4%`, `PODIUM 31%`, `POINTS 99%`

---
### Requirement: Focus driver highlights

The focus driver's timing row, its events in the intelligence panel and event history, and its markers on the event timeline SHALL be highlighted with the driver's team colour. Events not involving the focus driver SHALL remain visible without highlight.

#### Scenario: Highlighted event

- **WHEN** the focus driver is NOR and an `undercut_window` event lists drivers NOR and PIA
- **THEN** that event's card, history row, and timeline marker carry the NOR highlight
