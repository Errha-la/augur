# tyre-degradation Specification

## Purpose

Estimate how fast each driver's current tyres are losing performance and flag a sudden performance cliff, using only laps up to the current replay lap.

## Requirements

### Requirement: Stint degradation rate

For each driver's current stint, the system SHALL fit a least-squares line of fuel-corrected lap time (`lap_time_s + (0.03 * 110 / total_laps) * (lap - 1)`, i.e. 0.03 s per kg of a 110 kg fuel load burned evenly) against `tyre_life` over the stint's clean laps up to lap N, and SHALL report the slope as `deg_s_per_lap` and the number of clean laps as `deg_laps`. When the stint has fewer than 4 clean laps, `deg_s_per_lap` SHALL be null.

#### Scenario: Linear stint

##### Example: steady 0.1 s per lap

- **GIVEN** a stint with clean laps at `tyre_life` 2, 3, 4, 5, 6 and fuel-corrected times 95.0, 95.1, 95.2, 95.3, 95.4
- **WHEN** the degradation is fitted
- **THEN** `deg_s_per_lap` is 0.1 (to 3 decimals) and `deg_laps` is 5

#### Scenario: Short stint

- **WHEN** the current stint has 3 clean laps
- **THEN** `deg_s_per_lap` is null

---
### Requirement: Performance cliff detection

The system SHALL set `cliff` true when the current stint has at least 6 clean laps and both of the last 2 clean laps are more than 0.8 s slower than the line fitted on the stint's earlier clean laps. Otherwise `cliff` SHALL be false.

#### Scenario: Cliff detected

##### Example: last two laps fall off

- **GIVEN** 6 clean laps on a 0.05 s per lap line, followed by 2 clean laps 1.2 s and 1.5 s above that line
- **WHEN** the cliff check runs
- **THEN** `cliff` is true

#### Scenario: One slow lap only

- **WHEN** only the last clean lap is more than 0.8 s above the line
- **THEN** `cliff` is false
