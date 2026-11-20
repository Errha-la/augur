## Purpose

Put the most significant current analysis in the center of the dashboard and keep earlier analyses one click away, so the viewer always knows what matters now and how the race got here.

## ADDED Requirements

### Requirement: Primary event focus

The intelligence panel SHALL show the first event of the `/events?lap=N` response as the primary card, expanded with type label, lap, drivers, severity bar, title, What, Why, Next, and evidence. For `degradation_warning` and `undercut_window` the card SHALL request `/strategy?lap=<event lap>&driver=<first driver>` and show each strategy's name, mean time, p10-p90 range, and win probability, with "Simulating..." until the response arrives. When no events exist at lap N the panel SHALL show "No significant events yet".

#### Scenario: Newer event takes focus

- **WHEN** the lap moves from 14 to 15 and a `pace_drop` event appears at lap 15
- **THEN** the `pace_drop` event becomes the primary card and the previous primary moves to the event history

#### Scenario: Same lap ordering

##### Example: two events on one lap

- **GIVEN** at lap 22 a `position_change` with severity 40 and a `degradation_warning` with severity 80
- **WHEN** the lap is 22
- **THEN** the `degradation_warning` is primary and the `position_change` is the first history row

### Requirement: Collapsed event history

Every event at lap N or earlier other than the primary SHALL appear in the event history as a collapsed row showing lap, type label, and title, in the `/events` order. Clicking a row SHALL expand it in place with its What, Why, Next, and evidence; clicking again SHALL collapse it. Expanding a row SHALL NOT change the primary card.

#### Scenario: Focus driver events stay in race order

- **WHEN** the focus driver is involved in a lap 8 event and another driver in a lap 9 event
- **THEN** the history keeps lap order (lap 9 row before lap 8 row) and only the lap 8 row carries the focus highlight

#### Scenario: Expand a history row

- **WHEN** the viewer clicks the history row for a lap 8 event
- **THEN** that row shows its analysis and the primary card is unchanged

### Requirement: Event timeline navigation

The dashboard SHALL show a timeline from lap 1 to `total_laps` with one marker per event at lap N or earlier, positioned by lap and colored by event type. Clicking a marker SHALL set the current lap to that event's lap and stop playback.

#### Scenario: Jump to an event

- **WHEN** the current lap is 40 and the viewer clicks a marker at lap 12
- **THEN** the current lap becomes 12, playback stops, and the timeline shows only markers at laps up to 12
