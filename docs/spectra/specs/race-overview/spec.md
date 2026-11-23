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

A plotted driver's row SHALL be left off its solid line, appearing as a gap like a null lap time, when it is a non-racing lap: lap 1, a row with `pit_in` or `pit_out` true, or a row whose `track_status` is `4` (safety car), `5` (red flag), or `6` (virtual safety car). Each plotted driver's row with `pit_in` true SHALL be marked by the letter `P` at the top edge of the plot area on that lap, in that driver's line colour. Every lap from 1 to N on which at least one row of `/laps?lap=N` (any driver) has `track_status` `5`, `4`, or `6` SHALL be shaded across the plot height and labelled `RED`, `SC`, or `VSC`, taking the first of these present in that order; a run of consecutive laps with the same label SHALL show the label once, on its first lap. The y-axis range SHALL be computed from the lap times on the solid lines only. The legend SHALL add the key `P pit stop` when at least one `P` marker is drawn, and the key `SC / VSC` when at least one lap is shaded.

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

#### Scenario: Non-racing laps leave the line

- **WHEN** a plotted driver's rows include lap 1, a pit-in lap, a pit-out lap, or a lap under safety car, VSC, or red flag
- **THEN** those laps are gaps in that driver's solid line, and the laps before and after them are drawn

##### Example: LEC at Abu Dhabi 2024, lap 40

| LEC row | `lap_time_s` | Flags | On the solid line |
| ------- | ------------ | ----- | ----------------- |
| lap 1 | 98.031 | `track_status` 2 | no (lap 1) |
| lap 2 | 113.013 | `track_status` 6 | no (VSC) |
| lap 4 | 89.273 | `track_status` 1 | yes |
| lap 20 | 92.189 | `pit_in` | no |
| lap 21 | 108.662 | `pit_out` | no |
| lap 22 | 89.802 | `track_status` 1 | yes |

#### Scenario: Pit stop markers

- **WHEN** the chart at lap N plots LEC, SAI, and RUS, and their `pit_in` rows are laps 20, 25, and 26
- **THEN** a `P` in LEC's line colour is drawn at the top of lap 20, one in SAI's colour at lap 25, one in RUS's colour at lap 26, and the legend shows `P pit stop`

#### Scenario: Safety-car and VSC shading

- **WHEN** `/laps?lap=N` has rows with `track_status` `6` on laps 2 and 3 and no row with `4` or `5` on those laps
- **THEN** laps 2 and 3 are shaded, the label `VSC` appears once on lap 2, and the legend shows `SC / VSC`

##### Example: label per lap

| `track_status` values among the lap's rows | Shading |
| ------------------------------------------ | ------- |
| 1, 1, 2 | none |
| 1, 6, 6 | `VSC` |
| 6, 4 | `SC` |
| 4, 5 | `RED` |

#### Scenario: Y-axis from racing laps

- **WHEN** the solid-line lap times of the plotted drivers range from 88.2 s to 91.0 s with a median of 89.0 s, and their hidden out-laps are 108.7 s
- **THEN** the y-axis range is [87, 92], from `floor(88.2 − 0.5)` to `ceil(max(89.0 + 3, 88.2 + 2))`, and no hidden lap changes it
