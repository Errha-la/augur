## Purpose

Turn lap data, predictions, and degradation fits into a short list of significant race events, each explaining what happened, why, and what could happen next, so the dashboard shows meaning instead of raw numbers.

## ADDED Requirements

### Requirement: Detect race events lap by lap

An `EventEngine` built on a `RaceFeed` SHALL expose `step(lap)` that, for each lap N stepped in order, runs four detectors using only `feed.laps_until(N)`: `pace_drop`, `degradation_warning`, `undercut_window`, and `position_change`, with the trigger rules, deduplication, and severity scores defined in the design's rule-based event detectors table. A `degradation_warning` without a cliff SHALL require at least 8 clean laps in the stint. A `position_change` SHALL NOT fire for a driver whose own lap N is a pit-in or pit-out lap. Each event SHALL have `id` equal to `<race_id>:<lap>:<type>:<drivers joined by "-">`, and severity between 0 and 100.

#### Scenario: Out-of-order step

- **WHEN** `step(5)` is called after `step(3)` without `step(4)`
- **THEN** the engine raises an error naming the expected lap 4

#### Scenario: Pace drop

##### Example: 1.6 s slower than predicted

- **GIVEN** driver HAM is predicted at 95.0 s for clean lap 20 and runs 96.6 s
- **WHEN** detectors run at lap 20
- **THEN** a `pace_drop` event for HAM exists with severity 48

#### Scenario: Position change thresholds

- **WHEN** positions at lap N are compared with lap N-1
- **THEN** `position_change` events follow the thresholds below

##### Example: thresholds

| Change from lap N-1 to N | Event |
| ------------------------ | ----- |
| driver gains 1 place | none |
| driver loses 2 places | `position_change`, severity 40 |
| driver loses 3 places on their own pit-in lap | none |
| driver gains 2 places while two other cars pit | `position_change`, severity 40 |
| leader changes | `position_change`, severity 90 |
| any change on lap 1 | none |

#### Scenario: Degradation warning fires once per stint

- **WHEN** a driver's stint slope stays at or above 0.10 s per lap for laps 18 to 25 with at least 8 clean laps
- **THEN** exactly one non-cliff `degradation_warning` exists for that driver and stint

#### Scenario: Too few clean laps for a degradation warning

- **WHEN** a stint's slope is 0.30 s per lap over 7 clean laps and there is no cliff
- **THEN** no `degradation_warning` exists for that stint

### Requirement: Explained event analysis

Every event SHALL include `title` and `analysis` with non-empty `what`, `why`, and `next` sentences built from fixed templates and the event's `evidence` values. `degradation_warning` and `undercut_window` events SHALL name the best strategy from the Monte Carlo simulation in `next`. `next` SHALL be phrased as a conditional, probabilistic outlook and SHALL NOT be an imperative instruction. The same inputs SHALL produce identical text.

#### Scenario: Undercut analysis text

- **WHEN** an `undercut_window` event is created for NOR behind PIA
- **THEN** `what` names both drivers and the gap, `why` cites PIA's tyre age and degradation, and `next` names NOR's best strategy and its win probability

##### Example: outlook wording

- **GIVEN** NOR's best strategy is "pit on lap 21" with win probability 0.62
- **WHEN** the `next` text is built
- **THEN** it reads "Pitting on lap 21 is NOR's fastest option in 62% of simulations, which would put pressure on PIA." and contains no imperative such as "Pit now"

### Requirement: Precompute race events

`python -m augur.analyze --race <race_id> [--model <name>]` (default `lightgbm`) SHALL compute events by stepping an `EventEngine` over a `ReplayFeed` for laps 1 to `total_laps`, SHALL replace that race's rows for that model in the SQLite `events` table, SHALL record the run in the `analyses` table so a race analyzed with zero events reports `analyzed` true, and SHALL print `analyzed <race_id>: <n> events`. It SHALL exit with code 1 when the model file is missing or the race is in the model's training races.

#### Scenario: Re-run analysis

- **WHEN** the command runs twice for the same race
- **THEN** the `events` table holds the same events once, not twice

#### Scenario: Training race refused

- **WHEN** the race is listed in `train_races` of the metrics file
- **THEN** the command exits with code 1 and stores no events

### Requirement: Serve events up to a lap

`GET /api/races/{race_id}/events?lap=N` SHALL return `{race_id, lap, model, analyzed, events}` for the model named by `AUGUR_MODEL`, with only events whose lap is at most N, ordered by lap descending then severity descending. When the race has not been analyzed, `analyzed` SHALL be false and `events` empty. Events computed for lap N SHALL be identical when rows with lap greater than N are altered.

#### Scenario: Events filtered by lap

- **WHEN** events exist on laps 5, 12, and 30 and the client requests `lap=12`
- **THEN** the response contains the lap 12 event first, then the lap 5 event

#### Scenario: Altered future laps

- **WHEN** detectors run for laps 1 to N on fixture data, then rows with lap greater than N are altered and detectors run again
- **THEN** the events for laps 1 to N are identical
