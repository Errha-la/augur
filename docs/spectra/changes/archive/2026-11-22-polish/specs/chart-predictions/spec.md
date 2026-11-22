## Purpose

Let viewers see how close AUGUR's lap-time predictions were by drawing them next to the actual lap times.

## ADDED Requirements

### Requirement: Predicted lap lines

For each plotted driver and each lap k from 2 to the current lap N (lap 1 has no prediction), the lap-time chart SHALL draw the `predicted_next_lap_s` returned by `/predictions?lap=k-1` as a dashed line in the driver's team colour, using a per-race cache, and SHALL NOT request predictions for a lap greater than N.

#### Scenario: Cached history

- **WHEN** the viewer moves from lap 10 to lap 12 after the predictions for chart laps 2 to 10 were cached
- **THEN** the chart requests `/predictions?lap=10` and `/predictions?lap=11` only
