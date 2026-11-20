# replay-controls Specification

## Purpose

Let the viewer choose an ingested race and move through it lap by lap, manually or by playback, so every panel shows the race as it stood at that lap.

## Requirements

### Requirement: Race selection

On load the dashboard SHALL request `/api/races`, list the races by event name and year in a selector, select the first race, and set the lap to 1. Changing the selected race SHALL reset the lap to 1 and stop playback.

#### Scenario: Switch race

- **WHEN** the viewer selects another race while at lap 30
- **THEN** the lap becomes 1, playback stops, and all panels show the new race at lap 1

---
### Requirement: Lap navigation and playback

The dashboard SHALL provide a lap slider from 1 to `total_laps`, previous and next buttons, Left and Right arrow keys to step one lap, Space to toggle playback, and speeds 1×, 2×, 4× advancing one lap every 1000 ms, 500 ms, 250 ms. Playback SHALL stop at `total_laps`. On each lap change the dashboard SHALL fetch `state`, `laps`, `predictions`, `events`, and `positions` for that lap only, SHALL cancel requests for any earlier lap still in flight, and SHALL display a lap only after all five responses for that lap arrived.

#### Scenario: Step and bounds

- **WHEN** the viewer steps or playback ticks at the race boundaries
- **THEN** the lap stays within 1 to `total_laps`

##### Example: navigation cases

| Current lap | Action | Resulting lap |
| ----------- | ------ | ------------- |
| 1 | previous | 1 |
| 1 | Right arrow | 2 |
| 57 of 57 | next | 57 |
| 56 of 57, playing | one tick | 57 and playback stops |

#### Scenario: Fast slider move

- **WHEN** the viewer drags the slider from lap 5 to lap 40 quickly
- **THEN** only lap 40 data is displayed and no response for laps 6 to 39 is rendered

#### Scenario: No future requests

- **WHEN** the dashboard shows lap N
- **THEN** no request made for that view uses a `lap` parameter greater than N

---
### Requirement: Backend status messages

The dashboard SHALL show "Backend not reachable at /api. Start it with: uvicorn augur.api:app" with a Retry button when `/api/races` fails, "No races ingested. Run: python -m augur.ingest --year 2024 --rounds 1 24" when the race list is empty, and "Race not analyzed. Run: python -m augur.analyze --race <race_id>" in the intelligence panel when `/events` returns `analyzed` false.

#### Scenario: Backend down then retried

- **WHEN** `/api/races` fails and the viewer clicks Retry after the backend starts
- **THEN** the banner disappears and the first race loads at lap 1
