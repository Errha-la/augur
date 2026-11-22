# overcut-detection Specification

## Purpose

Point out when a driver can gain a place by staying out while the car ahead pits.

## Requirements

### Requirement: Overcut window event

The event engine SHALL emit `overcut_window` at lap N when the car directly ahead of driver D (order after lap N-1) has a `pit_in` on lap N, D has no `pit_in` on lap N, D was less than 3.0 s behind it at lap N-1, and D's `deg_s_per_lap` is below 0.05, at most once per pair per stop, with severity 55, a conditional What / Why / Next analysis that names D's best Monte Carlo strategy, and a null outcome.

#### Scenario: Overcut cases

- **WHEN** the car ahead of NOR pits on lap 20
- **THEN** an `overcut_window` event follows the cases below

##### Example: conditions

| Gap at lap 19 | NOR deg_s_per_lap | Event |
| ------------- | ----------------- | ----- |
| 2.1 s | 0.03 | yes, severity 55 |
| 3.4 s | 0.03 | no |
| 2.1 s | 0.08 | no |
| 2.1 s, NOR also pits on lap 20 | 0.03 | no |
