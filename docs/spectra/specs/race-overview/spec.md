# race-overview Specification

## Purpose

Show the state of every driver as a timing screen with AUGUR's finishing-position probabilities, plus recent lap times of the focus driver and neighbours at the selected lap, as the evidence layer under the intelligence panel.

## Requirements

### Requirement: Timing list

The dashboard SHALL show one row per driver ordered by `position` from `/state`, with a team-colour stripe from `team_color`, zero-padded position, driver code, tyre letter coloured by compound with tyre age, gap to leader, last lap time, predicted next lap time, degradation rate, a "CLIFF" tag when `cliff` is true, and `WIN` and `PODIUM` probabilities from `/positions` as whole percentages, showing `<1%` for values below 0.5%. Null values SHALL display as a dash. The last lap time SHALL be purple when it is the fastest clean lap of the race up to the current lap and green when it is that driver's fastest lap up to the current lap. Clicking a row SHALL make that driver the focus driver.

#### Scenario: Value formatting

- **WHEN** a row is rendered from `/state` and `/predictions` values
- **THEN** each field follows the formats below

##### Example: formatted fields

| Field | Value | Display |
| ----- | ----- | ------- |
| position | 3 | `03` |
| gap, leader | position 1 | `LEADER` |
| gap | 2.5 | `+2.500` |
| gap, lapped | `laps_behind_leader` 1 | `+1 LAP` |
| last lap | 96.512 | `1:36.512` |
| degradation | 0.082 | `+0.082/lap` |
| compound | MEDIUM, tyre age 7 | `M` in `#fbcc1c`, then `7` |
| predicted next lap | null | dash |
| podium probability | 0.418 | `42%` |
| win probability | 0.003 | `<1%` |

#### Scenario: Fastest lap colouring

- **WHEN** a last lap time is the race's or the driver's fastest so far
- **THEN** it is coloured purple or green as defined above

##### Example: two drivers

- **GIVEN** up to lap 10 the fastest clean lap of the race is VER 1:35.900 on lap 10, and HAM's best is 1:36.200 on lap 10
- **WHEN** the lap is 10
- **THEN** VER's last lap is purple and HAM's last lap is green

---
### Requirement: Lap-time chart

The dashboard SHALL plot actual lap times from `/laps?lap=N` as solid lines for the focus driver and the drivers directly ahead of and behind the focus driver at lap N, each in its team colour. Laps with null lap time SHALL appear as gaps. The focus driver's line SHALL be 3 px at full opacity and each neighbour's line 1.5 px at 75% opacity; a neighbour from the focus driver's team SHALL also show a dot at every plotted lap. The legend SHALL label every line with its driver code under the title `Neighbours at lap N`.

#### Scenario: Chart drivers

- **WHEN** the chart is drawn at lap N
- **THEN** it plots the focus driver and its neighbours as listed below

##### Example: neighbours

| Focus driver position at lap N | Drivers plotted |
| ------------------------------ | --------------- |
| 1 | focus, P2 |
| 5 | P4, focus, P6 |
| last (20) | P19, focus |

#### Scenario: Teammate neighbour

- **WHEN** the focus driver is HAM in P4 and RUS, also Mercedes, is in P5 at lap N
- **THEN** both lines use the Mercedes colour, HAM's line is 3 px with no dots, RUS's line is 1.5 px at 75% opacity with a dot at every plotted lap, and the legend lists HAM and RUS by code

#### Scenario: Neighbours follow the current lap

- **WHEN** the focus driver is in P5, P6 is ALO at lap 30, and P6 is GAS at lap 31
- **THEN** at lap 30 the chart plots ALO with laps 1 to 30 under the legend title `Neighbours at lap 30`, and at lap 31 it plots GAS with laps 1 to 31 under `Neighbours at lap 31`

#### Scenario: Chart stops at the current lap

- **WHEN** the current lap is 20
- **THEN** the chart's last plotted lap is 20 for every plotted driver
