## MODIFIED Requirements

### Requirement: Focus driver panel

The focus panel SHALL show the driver's code and team, a stint bar with one segment per stint up to the current lap (coloured by compound, width proportional to laps in the stint), `deg_s_per_lap` and the cliff flag, the predicted next lap, expected position with its p10-p90 range, `p_win`, `p_podium`, and `p_points`, a chart of `p_win` and `p_podium` for laps 1 to N from `/positions/history?lap=N`, the note "Includes random safety-car and VSC periods" under the probabilities, a strategy table from `/strategy?lap=N&driver=<focus>` with the note "Assumes a green race to the end" under it, and the list of events at lap N or earlier whose `drivers` include the focus driver. The strategy table and the probability history SHALL be requested when playback is paused, and during playback only on laps divisible by 5; it SHALL show "Simulating..." until the response arrives.

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

#### Scenario: Safety-car notes

- **WHEN** the focus panel renders with a strategy table
- **THEN** "Includes random safety-car and VSC periods" appears under the probabilities and "Assumes a green race to the end" appears under the strategy table, and no other copy of either note appears
