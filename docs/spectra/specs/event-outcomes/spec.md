# event-outcomes Specification

## Purpose

Check whether AUGUR's undercut and degradation calls came true, so every prediction can be judged, while keeping each verdict hidden during replay until the lap where it was decided.

## Requirements

### Requirement: Undercut outcome

For an `undercut_window` event at lap E with chaser C and target T, analysis SHALL set `outcome` to "hit" when C's computed position is ahead of T at lap E+8, "miss" when it is not, and "void" when the race has fewer than E+8 laps. `outcome_lap` SHALL be E+8 for hit and miss and `total_laps` for void, and `outcome_text` SHALL state the result in one sentence naming both drivers and the deciding lap.

#### Scenario: Undercut cases

- **WHEN** an `undercut_window` event at lap 18 for NOR behind PIA is resolved in a 57-lap race
- **THEN** the outcome follows the cases below

##### Example: outcome table

| Position at lap 26 | Race length | outcome | outcome_lap |
| ------------------ | ----------- | ------- | ----------- |
| NOR P3, PIA P4 | 57 | hit | 26 |
| NOR P4, PIA P3 | 57 | miss | 26 |
| any | 24 | void | 24 |

---
### Requirement: Degradation outcome

For a `degradation_warning` event at lap E for driver D, analysis SHALL set `outcome` to "hit" when D has a `pit_in` lap P with E < P <= E+8, "miss" when D completes lap E+8 without such a lap, and "void" when the race has fewer than E+8 laps and D did not pit. `outcome_lap` SHALL be P for a hit, E+8 for a miss, and `total_laps` for void.

#### Scenario: Pit inside the window

##### Example: pit on lap 23

- **GIVEN** a `degradation_warning` for HAM at lap 20 and HAM's `pit_in` lap is 23
- **WHEN** analysis resolves outcomes
- **THEN** `outcome` is "hit", `outcome_lap` is 23, and `outcome_text` is "HAM pitted on lap 23, 3 laps after the warning."

#### Scenario: No pit inside the window

- **WHEN** HAM next pits on lap 31 after a warning at lap 20
- **THEN** `outcome` is "miss" and `outcome_lap` is 28

---
### Requirement: Outcomes hidden until resolved

Events returned by `GET /api/races/{race_id}/events?lap=N` SHALL include `outcome`, `outcome_lap`, and `outcome_text`, and all three SHALL be null when `outcome_lap` is greater than N or the event type has no outcome rule.

#### Scenario: Before and after the deciding lap

- **WHEN** an event whose outcome was decided on lap 23 is requested at different laps
- **THEN** the outcome is revealed only from lap 23 on

##### Example: hit decided on lap 23

| Requested lap | outcome in response |
| ------------- | ------------------- |
| 22 | null |
| 23 | "hit" |
| 40 | "hit" |
